import asyncio
import hmac
import json
import logging
import os
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from tracing import configure
from releases import RELEASES
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, Response
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    ProcessCollector,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("demo")
logging.basicConfig(level=logging.INFO, format="%(message)s")


class Scenario(BaseModel):
    name: Literal[
        "healthy",
        "errors",
        "latency",
        "dependency_timeout",
        "database",
        "cpu",
        "memory",
        "deployment",
    ]
    duration_seconds: int = Field(default=30, ge=1, le=120)
    expected_revision: str | None = None


class RestartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: str = Field(min_length=1, max_length=64)
    expected_boot_id: str = Field(min_length=1, max_length=64)


class RollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: str = Field(min_length=1, max_length=64)
    expected_version: Literal["demo-v2"]
    target_version: Literal["demo-v1"]


class Checkout(BaseModel):
    product_id: Literal["book", "mug"]
    quantity: int = Field(default=1, ge=1, le=10)


def create_app(service=None, payment_transport=None, restart_callback=None):
    service = service or os.getenv("SERVICE_NAME", "checkout")
    app = FastAPI(title=f"Demo {service}")
    registry = CollectorRegistry()
    ProcessCollector(registry=registry)
    requests = Counter(
        "demo_requests_total",
        "Measured HTTP requests",
        ["service", "route", "status"],
        registry=registry,
    )
    duration = Histogram(
        "demo_request_duration_seconds",
        "Measured request duration",
        ["service", "route"],
        registry=registry,
    )
    failures = Counter(
        "demo_dependency_failures_total", "Payment failures", registry=registry
    )
    state = {"name": "healthy", "until": 0.0, "revision": str(uuid4())}
    previous_release = None
    boot_id = str(uuid4())
    boot_time = time.monotonic()
    restart_pending = False
    restart_enabled = os.getenv("DEMO_RESTART_ENABLED", "false") == "true"
    logs = deque(maxlen=100)
    events = deque(maxlen=30)
    orders = OrderedDict()
    workload_lock = asyncio.Lock()

    def active():
        return state["name"] if time.monotonic() < state["until"] else "healthy"

    def authorize(token):
        expected = os.getenv("DEMO_CONTROL_TOKEN", "")
        if not expected or not hmac.compare_digest(
            (token or "").encode("utf-8"), expected.encode("utf-8")
        ):
            raise HTTPException(403, "Invalid demo control token")

    @app.middleware("http")
    async def measure(request: Request, call_next):
        request_id = str(uuid4())
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        elapsed = time.perf_counter() - started
        if path != "/metrics":
            requests.labels(service, path, str(response.status_code)).inc()
            duration.labels(service, path).observe(elapsed)
            logger.info(
                json.dumps(
                    {
                        "service": service,
                        "request_id": request_id,
                        "route": path,
                        "status": response.status_code,
                        "duration_seconds": elapsed,
                    }
                )
            )
        trace_id = format(trace.get_current_span().get_span_context().trace_id, "032x")
        if path.startswith("/api/"):
            logs.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": service,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "route": path,
                    "status": response.status_code,
                    "duration_seconds": elapsed,
                }
            )
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health")
    async def health():
        return {"status": "alive", "service": service, "boot_id": boot_id}

    @app.get("/ready")
    async def ready():
        if active() in {"errors", "database", "deployment", "dependency_timeout"}:
            raise HTTPException(503, "Controlled demo failure active")
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics():
        return Response(
            generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST}
        )

    @app.get("/control/scenario")
    async def current(x_demo_token: str = Header(default="")):
        authorize(x_demo_token)
        return {
            "deployment_version": "demo-v2" if active() == "deployment" else "demo-v1",
            "previous_version": previous_release,
            "boot_id": boot_id,
            "restart_enabled": restart_enabled,
            "name": active(),
            "revision": state["revision"],
            "remaining_seconds": max(0, state["until"] - time.monotonic()),
            "simulated": True,
        }

    @app.post("/control/scenario")
    async def scenario(body: Scenario, x_demo_token: str = Header(default="")):
        nonlocal previous_release
        authorize(x_demo_token)
        if restart_pending:
            raise HTTPException(409, "Restart is pending")
        if (
            body.expected_revision is not None
            and body.expected_revision != state["revision"]
        ):
            raise HTTPException(409, "Scenario changed since approval")
        if body.name == "deployment" and active() != "deployment":
            previous_release = "demo-v1"
            events.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "demo_release_deployed",
                    "previous_version": previous_release,
                    "version": "demo-v2",
                    "scope": "bundled demo behavior",
                }
            )
        state.update(
            name=body.name,
            until=time.monotonic() + body.duration_seconds,
            revision=str(uuid4()),
        )
        events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "scenario_changed",
                "scenario": body.name,
                "revision": state["revision"],
                "simulated": True,
            }
        )
        return {"name": active(), "simulated": True}

    @app.post("/control/rollback")
    async def rollback(body: RollbackRequest, x_demo_token: str = Header(default="")):
        authorize(x_demo_token)
        if (
            restart_pending
            or body.expected_revision != state["revision"]
            or active() != "deployment"
            or body.target_version != previous_release
        ):
            raise HTTPException(
                409, "Recorded demo deployment changed or no previous release exists"
            )
        state.update(name="healthy", until=0.0, revision=str(uuid4()))
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "demo_release_rolled_back",
            "from_version": body.expected_version,
            "version": body.target_version,
            "revision": state["revision"],
            "scope": "bundled demo behavior, not container image rollback",
        }
        events.append(event)
        return event

    async def exit_for_restart():
        await asyncio.sleep(0.25)
        if restart_callback:
            restart_callback()
        else:
            # Fixed exit only; Docker on-failure restarts this disposable container.
            os._exit(75)

    @app.post("/control/restart", status_code=202)
    async def restart(
        body: RestartRequest,
        tasks: BackgroundTasks,
        x_demo_token: str = Header(default=""),
    ):
        nonlocal restart_pending
        authorize(x_demo_token)
        if not restart_enabled:
            raise HTTPException(
                409, "Restart is disabled outside the disposable Compose demo"
            )
        if time.monotonic() - boot_time < 10:
            raise HTTPException(409, "Wait for the demo startup safety window")
        if (
            restart_pending
            or body.expected_revision != state["revision"]
            or body.expected_boot_id != boot_id
        ):
            raise HTTPException(
                409, "Restart precondition changed or restart already pending"
            )
        restart_pending = True
        tasks.add_task(exit_for_restart)
        return {
            "status": "restart_requested",
            "previous_boot_id": boot_id,
            "ephemeral_data_lost": True,
        }

    @app.get("/control/evidence")
    async def evidence(x_demo_token: str = Header(default="")):
        authorize(x_demo_token)
        return {
            "logs": list(logs),
            "traces": list(app.state.trace_exporter.spans),
            "changes": list(events),
            "retention": "100 logs/spans, 30 change events; process lifetime",
        }

    async def apply_failure():
        name = active()
        RELEASES["demo-v2" if name == "deployment" else "demo-v1"]()
        if name in {"errors", "database"}:
            raise HTTPException(503, f"Simulated {name} failure")
        if name == "dependency_timeout":
            failures.inc()
            await asyncio.sleep(0.1)
            raise HTTPException(504, "Simulated payment timeout")
        if name == "latency":
            await asyncio.sleep(0.3)
        if name in {"cpu", "memory"}:
            if workload_lock.locked():
                raise HTTPException(429, "Demo workload already running")
            async with workload_lock:
                if name == "memory":
                    block = bytearray(8 * 1024 * 1024)
                    await asyncio.sleep(0.05)
                    del block
                else:

                    def bounded_cpu():
                        end = time.monotonic() + 0.05
                        while time.monotonic() < end:
                            sum(i * i for i in range(100))

                    await asyncio.to_thread(bounded_cpu)

    @app.get("/api/products")
    async def products():
        return [{"id": "book", "price_cents": 1500}, {"id": "mug", "price_cents": 800}]

    @app.post("/api/pay")
    async def pay():
        await apply_failure()
        return {"status": "paid", "simulated": True}

    @app.post("/api/checkout", status_code=201)
    async def checkout(body: Checkout):
        await apply_failure()
        try:
            async with httpx.AsyncClient(
                transport=payment_transport, timeout=1.0
            ) as client:
                HTTPXClientInstrumentor.instrument_client(
                    client, tracer_provider=app.state.trace_provider
                )
                result = await client.post(
                    os.getenv("PAYMENT_URL", "http://payment:8000") + "/api/pay"
                )
                result.raise_for_status()
        except httpx.HTTPError:
            failures.inc()
            raise HTTPException(502, "Payment dependency unavailable") from None
        order_id = str(uuid4())
        orders[order_id] = {
            "id": order_id,
            **body.model_dump(),
            "status": "paid",
            "simulated": True,
        }
        if len(orders) > 1000:
            orders.popitem(last=False)
        return orders[order_id]

    @app.get("/api/orders/{order_id}")
    async def order(order_id: str):
        if order_id not in orders:
            raise HTTPException(404, "Order not found (demo orders are ephemeral)")
        return orders[order_id]

    configure(app, service)
    return app


app = create_app()

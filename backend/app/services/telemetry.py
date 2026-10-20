"""Only fixed queries and fixed internal targets; no user-supplied URLs/PromQL."""

import asyncio
import math
from datetime import datetime, timezone
import httpx
from pydantic import BaseModel


class Observation(BaseModel):
    service: str
    observed_at: str
    health: str
    ready: bool | None
    telemetry_status: str
    request_rate: float | None = None
    error_rate: float | None = None
    latency_p95: float | None = None
    request_count_window: float | None = None
    missing: list[str] = []


async def scalar(client, base, query):
    response = await client.get(
        base + "/api/v1/query", params={"query": query, "timeout": "2s"}
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success":
        raise ValueError("Query failed")
    rows = payload["data"]["result"]
    if not rows:
        return None
    value = float(rows[0]["value"][1])
    return value if math.isfinite(value) else None


async def observe(config, service, client):
    target = config.targets[service]
    missing = []
    try:
        response = await client.get(target + "/health")
        health = "healthy" if response.status_code == 200 else "unavailable"
    except httpx.HTTPError:
        health = "unavailable"
    try:
        ready = (await client.get(target + "/ready")).status_code == 200
    except httpx.HTTPError:
        ready = None
    label = f'service="{service}",route=~"/api/checkout|/api/pay"'
    total = f"sum(rate(demo_requests_total{{{label}}}[1m]))"
    queries = {
        "request_rate": total,
        "request_count_window": f"sum(increase(demo_requests_total{{{label}}}[1m]))",
        "error_rate": f'(sum(rate(demo_requests_total{{{label},status=~"5.."}}[1m])) or vector(0)) / ({total})',
        "latency_p95": f"histogram_quantile(0.95, sum by (le) (rate(demo_request_duration_seconds_bucket{{{label}}}[1m])))",
    }
    results = await asyncio.gather(
        *(scalar(client, config.prometheus_url, q) for q in queries.values()),
        return_exceptions=True,
    )
    values = {}
    for key, result in zip(queries, results):
        if isinstance(result, Exception):
            values[key] = None
            missing.append(key)
        else:
            values[key] = result
    return Observation(
        service=service,
        observed_at=datetime.now(timezone.utc).isoformat(),
        health=health,
        ready=ready,
        telemetry_status="unavailable" if missing else "available",
        missing=missing,
        **values,
    )

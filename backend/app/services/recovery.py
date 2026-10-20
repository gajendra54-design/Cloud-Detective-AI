import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
import httpx
from prometheus_client.parser import text_string_to_metric_families


def fingerprint(action, target, parameters, version):
    return hashlib.sha256(
        json.dumps([action, target, parameters, version], sort_keys=True).encode()
    ).hexdigest()


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def approved(action, incident):
    return (
        action.status == "APPROVED"
        and action.approved_by is not None
        and action.action
        in {"disable_failure", "health_check", "restart_service", "rollback_demo"}
        and action.target == incident.service_id
        and action.incident_version == incident.version
        and incident.status == "OPEN"
        and utc(action.expires_at) > datetime.now(timezone.utc)
        and action.fingerprint
        == fingerprint(
            action.action, action.target, action.parameters, action.incident_version
        )
    )


def counters(text):
    total = errors = 0
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            if sample.name == "demo_requests_total" and sample.labels.get("route") in {
                "/api/checkout",
                "/api/pay",
            }:
                total += sample.value
                if sample.labels.get("status", "").startswith("5"):
                    errors += sample.value
    return total, errors


async def verify(config, target, client, interval=1):
    base = config.targets[target]
    samples = []
    try:
        before_response = await client.get(base + "/metrics")
        before_response.raise_for_status()
        before = counters(before_response.text)
        for _ in range(3):
            started = time.perf_counter()
            response = await client.post(
                base + ("/api/checkout" if target == "checkout" else "/api/pay"),
                json={"product_id": "book"} if target == "checkout" else None,
            )
            latency = time.perf_counter() - started
            ready = (await client.get(base + "/ready")).status_code == 200
            dependency = (
                (await client.get(config.payment_url + "/ready")).status_code == 200
                if target == "checkout"
                else True
            )
            samples.append(
                {
                    "status": response.status_code,
                    "latency_seconds": latency,
                    "ready": ready,
                    "dependency_ready": dependency,
                }
            )
            await asyncio.sleep(interval)
        after_response = await client.get(base + "/metrics")
        after_response.raise_for_status()
        after = counters(after_response.text)
        total, errors = after[0] - before[0], after[1] - before[1]
        passed = (
            total >= 3
            and errors == 0
            and all(
                s["status"] in {200, 201}
                and s["ready"]
                and s["dependency_ready"]
                and s["latency_seconds"] < config.latency_threshold
                for s in samples
            )
        )
        return {
            "passed": passed,
            "samples": samples,
            "new_requests": total,
            "new_errors": errors,
            "method": "Three fresh business requests, readiness, dependency readiness and independent metrics counter delta",
            "limitations": "Short local demo window; historical Prometheus rate may take one minute to clear",
        }
    except (httpx.HTTPError, ValueError):
        return {
            "passed": False,
            "samples": samples,
            "reason": "Verification telemetry unavailable or timed out",
        }


async def restart_demo(config, target, parameters, client):
    base = config.targets[target]
    old_boot = parameters["expected_boot_id"]
    response = await client.post(
        base + "/control/restart",
        headers={"X-Demo-Token": config.control_token},
        json={
            "expected_revision": parameters["expected_revision"],
            "expected_boot_id": old_boot,
        },
    )
    response.raise_for_status()
    # Acceptance is not proof of restart. Require a distinct process identity.
    for _ in range(20):
        await asyncio.sleep(0.5)
        try:
            health = await client.get(base + "/health")
            health.raise_for_status()
            boot = health.json().get("boot_id")
            if boot and boot != old_boot:
                return {"previous_boot_id": old_boot, "new_boot_id": boot}
        except (httpx.HTTPError, ValueError):
            continue
    raise ValueError("No new process identity observed after restart")

"""Verify Stage 1 against running local containers; writes no secrets."""

import json
import os
import time
from pathlib import Path
import httpx


def main():
    token = os.getenv("DEMO_CONTROL_TOKEN")
    if not token:
        for line in (
            (Path(__file__).resolve().parents[1] / ".env").read_text().splitlines()
        ):
            if line.startswith("DEMO_CONTROL_TOKEN="):
                token = line.split("=", 1)[1]
    if not token:
        raise RuntimeError("DEMO_CONTROL_TOKEN required")
    results = []
    with httpx.Client(timeout=10, trust_env=False) as client:
        base = "http://127.0.0.1:8001"
        headers = {"X-Demo-Token": token}

        def scenario(name, duration=30):
            response = client.post(
                base + "/control/scenario",
                headers=headers,
                json={"name": name, "duration_seconds": duration},
            )
            response.raise_for_status()

        try:
            assert client.get("http://127.0.0.1:8000/api/v1/ready").status_code == 200
            inventory = client.get("http://127.0.0.1:8000/api/v1/services")
            inventory.raise_for_status()
            assert {s["id"] for s in inventory.json()} == {"checkout", "payment"}
            results.append(
                "PASS: PostgreSQL-backed service inventory and backend readiness"
            )
            assert (
                client.post(
                    base + "/control/scenario", json={"name": "errors"}
                ).status_code
                == 403
            )
            for name, status in [
                ("healthy", 201),
                ("errors", 503),
                ("database", 503),
                ("deployment", 503),
                ("dependency_timeout", 504),
                ("latency", 201),
                ("cpu", 201),
                ("memory", 201),
            ]:
                scenario(name)
                started = time.perf_counter()
                response = client.post(
                    base + "/api/checkout", json={"product_id": "book"}
                )
                elapsed = time.perf_counter() - started
                assert response.status_code == status, (name, response.status_code)
                if name == "latency":
                    assert elapsed >= 0.28
                results.append(f"PASS: {name}, HTTP {status}")
                scenario("healthy")
                assert (
                    client.post(
                        base + "/api/checkout", json={"product_id": "mug"}
                    ).status_code
                    == 201
                )
            scenario("errors", 1)
            time.sleep(1.1)
            assert client.get(base + "/ready").status_code == 200
            results.append("PASS: expiry and unauthorized activation rejection")
            metrics = client.get(base + "/metrics").text
            assert "demo_request_duration_seconds_bucket" in metrics
            assert "process_resident_memory_bytes" in metrics
            assert "demo_dependency_failures_total" in metrics
            deadline = time.monotonic() + 30
            while True:
                targets = client.get("http://127.0.0.1:9090/api/v1/targets").json()[
                    "data"
                ]["activeTargets"]
                if len(targets) == 2 and all(t["health"] == "up" for t in targets):
                    break
                if time.monotonic() >= deadline:
                    break
                time.sleep(1)
            assert len(targets) == 2 and all(t["health"] == "up" for t in targets)
            results.append("PASS: measured metrics and both Prometheus targets up")
        finally:
            scenario("healthy")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

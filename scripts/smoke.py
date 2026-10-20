"""Run against the live Compose stack. Requires DEMO_CONTROL_TOKEN."""

import os
import httpx

with httpx.Client(base_url="http://localhost:8001", timeout=5) as client:
    headers = {"X-Demo-Token": os.environ["DEMO_CONTROL_TOKEN"]}

    def set_scenario(name):
        result = client.post(
            "/control/scenario",
            headers=headers,
            json={"name": name, "duration_seconds": 30},
        )
        result.raise_for_status()

    try:
        set_scenario("healthy")
        assert (
            client.post("/api/checkout", json={"product_id": "book"}).status_code == 201
        )
        set_scenario("errors")
        assert (
            client.post("/api/checkout", json={"product_id": "book"}).status_code == 503
        )
        set_scenario("healthy")
        for _ in range(3):
            assert (
                client.post("/api/checkout", json={"product_id": "book"}).status_code
                == 201
            )
        assert "demo_requests_total" in client.get("/metrics").text
        print("PASS: live baseline, failure, recovery requests, metrics")
    finally:
        set_scenario("healthy")

"""Bounded live PostgreSQL/HTTP race test; only disposable checkout is changed."""

import concurrent.futures
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000/api/v1"


def main():
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    inv = {"Authorization": "Bearer " + values["INVESTIGATOR_TOKEN"]}
    approver = {"Authorization": "Bearer " + values["APPROVER_TOKEN"]}
    report = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "parallel_requests": 8,
        "scope": "Concurrent HTTP requests against one backend process and real PostgreSQL; not multi-worker or sustained-load validation",
    }

    def burst(path, headers, body=None):
        barrier = threading.Barrier(8)

        def call(_):
            with httpx.Client(base_url=BASE, timeout=45, trust_env=False) as client:
                barrier.wait(timeout=15)
                response = client.post(path, headers=headers, json=body or {})
                return response.status_code, response.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            return list(pool.map(call, range(8)))

    with httpx.Client(base_url=BASE, timeout=45, trust_env=False) as client:

        def post(path, headers=inv, body=None):
            response = client.post(path, headers=headers, json=body or {})
            response.raise_for_status()
            return response.json()

        try:
            post("/demo/scenario", body={"name": "errors", "duration_seconds": 120})
            print("Waiting for a real readiness incident...", flush=True)
            deadline = time.monotonic() + 105
            incident = None
            while time.monotonic() < deadline:
                incident = next(
                    (
                        r
                        for r in client.get("/incidents").json()
                        if r["service_id"] == "checkout"
                        and r["rule"] == "service_not_ready"
                        and r["status"] == "OPEN"
                    ),
                    None,
                )
                if incident:
                    break
                time.sleep(2)
            assert incident, "No detector-created incident"
            incident_id = incident["id"]
            post("/demo/scenario", body={"name": "errors", "duration_seconds": 120})
            post(f"/incidents/{incident_id}/investigate")
            proposals = burst(f"/incidents/{incident_id}/propose", inv)
            assert all(status == 200 for status, _ in proposals), proposals
            ids = {body["id"] for _, body in proposals}
            assert len(ids) == 1, "Concurrent proposals created duplicate action IDs"
            action = proposals[0][1]
            assert action["action"] == "disable_failure"
            route = f'/remediations/{action["id"]}'
            approvals = burst(
                route + "/approve", approver, {"fingerprint": action["fingerprint"]}
            )
            assert sum(status == 200 for status, _ in approvals) == 1, approvals
            assert all(status in (200, 409) for status, _ in approvals)
            executions = burst(route + "/execute", approver)
            assert all(status in (200, 409) for status, _ in executions), executions
            final = post(route + "/execute", approver)
            assert final["status"] == "SUCCEEDED", final
            assert final["result"]["new_requests"] == 3
            timeline = client.get(f"/incidents/{incident_id}/timeline").json()
            for kind in ("proposed", "approved", "executing", "verification_completed"):
                assert (
                    sum(
                        row["details"].get("type") == kind
                        and row["details"].get("action_id") == action["id"]
                        for row in timeline
                    )
                    == 1
                ), kind
            assert (
                client.get(f"/incidents/{incident_id}").json()["status"] == "RESOLVED"
            )
            report.update(
                passed=True,
                incident_id=incident_id,
                action_id=action["id"],
                unique_proposals=len(ids),
                successful_approvals=sum(status == 200 for status, _ in approvals),
                execution_http_statuses=[status for status, _ in executions],
                fresh_requests=final["result"]["new_requests"],
                single_execution_timeline=True,
            )
            print(
                "PASS: eight concurrent proposals, approvals and executions produced one action and one verified execution",
                flush=True,
            )
        finally:
            post("/demo/scenario", body={"name": "healthy"})
    (ROOT / "docs/concurrency-verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

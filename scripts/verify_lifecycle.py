"""Live end-to-end test: failure -> detect -> investigate -> approve -> failed/successful recovery.
Only the two disposable Docker demo services are modified. Always restores healthy mode.
"""

import json
import subprocess
import time
from pathlib import Path
import httpx


def main():
    root = Path(__file__).resolve().parents[1]
    values = dict(
        line.split("=", 1)
        for line in (root / ".env").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    inv = {"Authorization": "Bearer " + values["INVESTIGATOR_TOKEN"]}
    approver = {"Authorization": "Bearer " + values["APPROVER_TOKEN"]}

    def payment(name):
        code = (
            "import os,httpx; r=httpx.post('http://localhost:8000/control/scenario',headers={'X-Demo-Token':os.environ['DEMO_CONTROL_TOKEN']},json={'name':"
            + repr(name)
            + ",'duration_seconds':120}); r.raise_for_status()"
        )
        subprocess.run(
            ["docker", "compose", "exec", "-T", "payment", "python", "-c", code],
            cwd=root,
            check=True,
            capture_output=True,
        )

    results = []
    with httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1", timeout=45, trust_env=False
    ) as client:

        def post(path, headers=inv, body=None):
            response = client.post(path, headers=headers, json=body or {})
            response.raise_for_status()
            return response.json()

        def scenario(name):
            return post("/demo/scenario", body={"name": name, "duration_seconds": 120})

        def prepare(incident):
            finding = post(f"/incidents/{incident}/investigate")
            evidence = client.get(f"/incidents/{incident}/evidence").json()
            assert set(finding["findings"]["supporting_evidence_ids"]) <= {
                e["id"] for e in evidence
            }
            action = post(f"/incidents/{incident}/propose")
            route = f'/remediations/{action["id"]}'
            denied = client.post(
                route + "/approve",
                headers=inv,
                json={"fingerprint": action["fingerprint"]},
            )
            assert denied.status_code == 403
            post(route + "/approve", approver, {"fingerprint": action["fingerprint"]})
            return action, route

        try:
            payment("healthy")
            scenario("errors")
            post("/demo/traffic")
            print("Waiting for real detector observations...", flush=True)
            deadline = time.monotonic() + 60
            incident = None
            while time.monotonic() < deadline:
                rows = client.get("/incidents").json()
                incident = next(
                    (
                        i
                        for i in rows
                        if i["service_id"] == "checkout"
                        and i["status"] == "OPEN"
                        and i["rule"] == "service_not_ready"
                    ),
                    None,
                )
                if incident:
                    break
                time.sleep(2)
            assert incident, "No detected incident within 60 seconds"
            incident_id = incident["id"]
            results.append(
                "PASS: actual detector created/reused an open readiness incident"
            )
            action, route = prepare(incident_id)
            results.append(
                "PASS: evidence-grounded diagnosis and backend role separation"
            )
            payment("errors")
            failed = post(route + "/execute", approver)
            assert failed["status"] == "FAILED", failed
            assert failed["result"]["passed"] is False
            assert client.get("/incidents/" + incident_id).json()["status"] == "OPEN"
            results.append(
                "PASS: executor succeeded but dependency verification failed; incident stayed open"
            )
            payment("healthy")
            scenario("errors")
            action, route = prepare(incident_id)
            success = post(route + "/execute", approver)
            assert success["status"] == "SUCCEEDED", success
            assert success["result"]["new_requests"] >= 3
            assert success["result"]["new_errors"] == 0
            assert (
                client.get("/incidents/" + incident_id).json()["status"] == "RESOLVED"
            )
            repeated = post(route + "/execute", approver)
            assert repeated["result"] == success["result"]
            results.append(
                "PASS: independently verified recovery and idempotent execution replay"
            )
            events = client.get("/incidents/" + incident_id + "/timeline").json()
            assert any(e["details"].get("passed") is False for e in events)
            assert any(e["details"].get("passed") is True for e in events)
            audit = client.get("/audit-events").json()
            assert any(
                e["subject"] == action["id"] and e["event"] == "verification_completed"
                for e in audit
            )
            results.append("PASS: persistent timeline and audit record both outcomes")
            report = {
                "results": results,
                "incident_id": incident_id,
                "action_id": action["id"],
                "verification": success["result"],
            }
            (root / "docs" / "live-verification.json").write_text(
                json.dumps(report, indent=2)
            )
            print(json.dumps(report, indent=2))
        finally:
            try:
                payment("healthy")
            finally:
                scenario("healthy")


if __name__ == "__main__":
    main()

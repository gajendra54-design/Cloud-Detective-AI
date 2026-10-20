"""Live approved process restart and bundled demo release rollback; no fake incidents."""

import json
import time
from datetime import datetime, timezone
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
    report = {"verified_at": datetime.now(timezone.utc).isoformat(), "actions": []}
    with httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1", timeout=45, trust_env=False
    ) as client:

        def post(path, body=None, headers=inv):
            response = client.post(path, headers=headers, json=body or {})
            response.raise_for_status()
            return response.json()

        try:
            for action_type, scenario in [
                ("restart_service", "errors"),
                ("rollback_demo", "deployment"),
            ]:
                post("/demo/scenario", {"name": scenario, "duration_seconds": 120})
                post("/demo/traffic")
                print("Waiting for a detected incident for " + action_type, flush=True)
                deadline = time.monotonic() + 105
                incident = None
                while time.monotonic() < deadline:
                    incident = next(
                        (
                            row
                            for row in client.get("/incidents").json()
                            if row["service_id"] == "checkout"
                            and row["status"] == "OPEN"
                        ),
                        None,
                    )
                    if incident:
                        break
                    time.sleep(2)
                assert incident, "No observed incident within detection window"
                # Refresh the bounded scenario after any cooldown waiting.
                post("/demo/scenario", {"name": scenario, "duration_seconds": 120})
                post(f'/incidents/{incident["id"]}/investigate')
                action = post(
                    f'/incidents/{incident["id"]}/propose', {"action": action_type}
                )
                assert action["action"] == action_type
                route = f'/remediations/{action["id"]}'
                assert (
                    client.post(
                        route + "/execute", headers=approver, json={}
                    ).status_code
                    == 409
                )
                post(
                    route + "/approve", {"fingerprint": action["fingerprint"]}, approver
                )
                result = post(route + "/execute", headers=approver)
                assert result["status"] == "SUCCEEDED", result
                assert result["result"]["passed"]
                if action_type == "restart_service":
                    restart = result["result"]["restart"]
                    assert restart["new_boot_id"] != restart["previous_boot_id"]
                else:
                    assert result["result"]["rollback"]["version"] == "demo-v1"
                replay = post(route + "/execute", headers=approver)
                assert replay["result"] == result["result"]
                assert (
                    client.get(f'/incidents/{incident["id"]}').json()["status"]
                    == "RESOLVED"
                )
                report["actions"].append(
                    {
                        "action": action_type,
                        "id": action["id"],
                        "incident_id": incident["id"],
                        "result": result["result"],
                        "replay": "PASS",
                    }
                )
                print(action_type + ": PASS", flush=True)
        finally:
            post("/demo/scenario", {"name": "healthy"})
    (root / "docs/recovery-actions-verification.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print("Live recovery action verification passed")


if __name__ == "__main__":
    main()

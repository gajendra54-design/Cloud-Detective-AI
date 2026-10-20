from pathlib import Path
import httpx

root = Path(__file__).resolve().parents[1]
values = dict(
    line.split("=", 1)
    for line in (root / ".env").read_text().splitlines()
    if "=" in line and not line.startswith("#")
)
with httpx.Client(
    base_url="http://127.0.0.1:8000/api/v1", timeout=30, trust_env=False
) as client:

    def post(path, role="INVESTIGATOR_TOKEN", body=None):
        response = client.post(
            path, headers={"Authorization": "Bearer " + values[role]}, json=body or {}
        )
        response.raise_for_status()
        return response.json()

    count = 0
    for incident in client.get("/incidents").json():
        if incident["status"] != "OPEN":
            continue
        post("/incidents/" + incident["id"] + "/investigate")
        action = post("/incidents/" + incident["id"] + "/propose")
        assert action["action"] == "health_check", "Expected healthy demo precondition"
        route = "/remediations/" + action["id"]
        post(
            route + "/approve", "APPROVER_TOKEN", {"fingerprint": action["fingerprint"]}
        )
        result = post(route + "/execute", "APPROVER_TOKEN")
        assert result["status"] == "SUCCEEDED", result
        count += 1
    print(
        f"PASS: {count} remaining demo incidents independently verified and resolved through approved health-check actions"
    )

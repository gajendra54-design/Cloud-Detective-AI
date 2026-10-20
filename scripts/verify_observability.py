"""Confirm real cross-service traces and the provisioned Grafana dashboard."""

import json
import subprocess
from pathlib import Path
import httpx

root = Path(__file__).resolve().parents[1]
values = dict(
    line.split("=", 1)
    for line in (root / ".env").read_text().splitlines()
    if "=" in line and not line.startswith("#")
)
with httpx.Client(timeout=10, trust_env=False) as client:
    response = client.post(
        "http://127.0.0.1:8001/api/checkout", json={"product_id": "book"}
    )
    response.raise_for_status()
    trace = response.headers["X-Trace-ID"]
    assert int(trace, 16) > 0
    data = client.get(
        "http://127.0.0.1:8001/control/evidence",
        headers={"X-Demo-Token": values["DEMO_CONTROL_TOKEN"]},
    ).json()
    assert any(span["trace_id"] == trace for span in data["traces"])
    code = (
        "import os,json,httpx; d=httpx.get('http://localhost:8000/control/evidence',headers={'X-Demo-Token':os.environ['DEMO_CONTROL_TOKEN']}).json(); print(json.dumps({'matched':sum(s['trace_id']=="
        + repr(trace)
        + " for s in d['traces'])}))"
    )
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "payment", "python", "-c", code],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["matched"] > 0
    dashboard = client.get(
        "http://127.0.0.1:3000/api/dashboards/uid/cloud-detective",
        auth=("admin", values["GRAFANA_PASSWORD"]),
    )
    dashboard.raise_for_status()
    assert len(dashboard.json()["dashboard"]["panels"]) == 4
    report = {
        "cross_service_trace_id": trace,
        "checkout_and_payment_share_trace": True,
        "grafana_panels": 4,
    }
    (root / "docs" / "observability-verification.json").write_text(
        json.dumps(report, indent=2)
    )
    print(
        "PASS: checkout/payment share a real OpenTelemetry trace; Grafana dashboard has four provisioned panels"
    )

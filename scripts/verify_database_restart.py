"""Briefly stop local PostgreSQL; verify recovery without restarting the backend."""

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def compose(*args):
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()


def query(sql):
    return compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "detective",
        "-d",
        "detective",
        "-Atc",
        sql,
    )


def snapshot():
    return {
        table: set(query(f"SELECT id FROM {table}").splitlines())
        for table in ("incidents", "timeline_events", "audit_events", "users")
    }


def main():
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "status": "FAILED"}
    try:
        with httpx.Client(
            base_url="http://127.0.0.1:8000/api/v1", timeout=10, trust_env=False
        ) as client:
            client.get("/ready").raise_for_status()
            before = snapshot()
            backend_id = compose("ps", "-q", "backend")
            started = subprocess.check_output(
                ["docker", "inspect", "--format", "{{.State.StartedAt}}", backend_id],
                text=True,
                timeout=15,
            ).strip()
            try:
                compose("stop", "-t", "10", "postgres")
                assert client.get("/ready").status_code == 503, "Readiness must fail"
                assert (
                    client.get("/health").status_code == 200
                ), "Liveness must remain up"
                report["outage_checks"] = "readiness 503; liveness 200"
            finally:
                # Restore even when an outage assertion fails.
                compose("start", "postgres")
            deadline = time.monotonic() + 60
            while client.get("/ready").status_code != 200:
                if time.monotonic() >= deadline:
                    raise AssertionError("Backend did not reconnect within 60 seconds")
                time.sleep(1)
            after = snapshot()
            assert all(before[t] <= after[t] for t in before), "Persistent records lost"
            restored_at = query("SELECT CURRENT_TIMESTAMP")
            deadline = time.monotonic() + 30
            while (
                query(
                    "SELECT count(*) FROM telemetry_samples WHERE created_at > '"
                    + restored_at
                    + "'::timestamptz"
                )
                == "0"
            ):
                if time.monotonic() >= deadline:
                    raise AssertionError("Monitor did not resume writing telemetry")
                time.sleep(1)
            assert compose("ps", "-q", "backend") == backend_id
            current_start = subprocess.check_output(
                ["docker", "inspect", "--format", "{{.State.StartedAt}}", backend_id],
                text=True,
                timeout=15,
            ).strip()
            assert current_start == started, "Backend restarted instead of reconnecting"
            report.update(
                status="PASSED",
                preserved_records={t: len(before[t]) for t in before},
                backend_restarted=False,
                monitor_resumed=True,
                limitations="Graceful single-node database outage; not crash consistency or distributed failover",
            )
    finally:
        (ROOT / "docs/database-restart-verification.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

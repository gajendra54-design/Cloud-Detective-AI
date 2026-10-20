"""Validate an installed local Ollama model against persisted real incident evidence."""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.investigation import investigate, validate_finding, diagnose  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--timeout", type=int, default=180, choices=range(5, 181), metavar="5..180"
    )
    args = parser.parse_args()
    with httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1", timeout=10, trust_env=False
    ) as client:
        response = client.get("/incidents")
        response.raise_for_status()
        incidents = response.json()
        assert (
            incidents
        ), "Run the incident demonstration first; no fake evidence is generated"
        incident = incidents[0]
        response = client.get(f'/incidents/{incident["id"]}/evidence')
        response.raise_for_status()
        rows = response.json()
        evidence = []
        for kind in ("observation", "scenario"):
            row = next((r for r in reversed(rows) if r["kind"] == kind), None)
            assert row, "Investigate the incident first"
            evidence.append(row)
    os.environ.update(
        AI_PROVIDER="ollama",
        OLLAMA_URL="http://127.0.0.1:11434",
        OLLAMA_MODEL=args.model,
        AI_TIMEOUT_SECONDS=str(args.timeout),
    )
    print(
        "Testing installed local model against retained incident evidence...",
        flush=True,
    )
    started = time.monotonic()
    finding, provider = asyncio.run(investigate(evidence))
    validate_finding(finding.model_dump(), evidence)
    baseline = diagnose(evidence)
    report = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "provider": provider,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "incident_id": incident["id"],
        "evidence_ids": [e["id"] for e in evidence],
        "live_model_passed": provider == "ollama-guarded",
        "guardrails_passed": finding.summary == baseline.summary
        and finding.expected_recovery == baseline.expected_recovery
        and finding.abort_conditions == baseline.abort_conditions
        and "Three fresh" in finding.expected_recovery
        and finding.probable_cause.startswith("AI hypothesis (unverified):"),
        "finding": finding.model_dump(),
        "scope": "Retained real demo evidence; schema and citations validated, not a benchmark or causal-accuracy evaluation",
    }
    (ROOT / "docs/live-ai-verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "finding"}, indent=2))
    if not report["guardrails_passed"]:
        raise SystemExit("Factual or recovery-policy guardrails failed")
    if provider != "ollama-guarded":
        raise SystemExit(
            "Live model did not validate; fallback was retained and recorded"
        )


if __name__ == "__main__":
    main()

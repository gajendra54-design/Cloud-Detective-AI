"""Scan all Compose runtime images with Docker Scout; save reproducible reports."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = [
    "cloud-detective-ai-backend:latest",
    "cloud-detective-ai-frontend:latest",
    "cloud-detective-ai-checkout:latest",
    "cloud-detective-ai-payment:latest",
    "cloud-detective-ai-postgres:latest",
    "prom/prometheus:v3.13.4",
    "grafana/grafana:13.2.4",
]


def run(args, timeout=300):
    return subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def main():
    directory = ROOT / "docs/image-scans"
    directory.mkdir(exist_ok=True)
    report = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "scanner": "Docker Scout",
        "images": [],
    }
    failed = False
    for image in IMAGES:
        name = image.replace("/", "-").replace(":", "-")
        path = directory / (name + ".sarif.json")
        print("Scanning " + image, flush=True)
        identity = run(["docker", "image", "inspect", "--format", "{{.Id}}", image])
        entry = {
            "image": image,
            "image_id": identity.stdout.strip(),
            "report": str(path.relative_to(ROOT)).replace("\\", "/"),
        }
        try:
            scan = run(
                [
                    "docker",
                    "scout",
                    "cves",
                    "local://" + image,
                    "--format",
                    "sarif",
                    "--output",
                    str(path),
                ]
            )
            if scan.returncode != 0:
                entry.update(status="SCAN_FAILED", reason=scan.stderr[-2000:])
                failed = True
            else:
                data = json.loads(path.read_text(encoding="utf-8"))
                results = [
                    r
                    for batch in data.get("runs", [])
                    for r in batch.get("results", [])
                ]
                levels = {}
                for result in results:
                    level = result.get("level", "unspecified")
                    levels[level] = levels.get(level, 0) + 1
                severity_counts = {}
                fixable = 0
                for batch in data.get("runs", []):
                    for rule in batch["tool"]["driver"].get("rules", []):
                        properties = rule.get("properties", {})
                        severity = properties.get("cvssV3_severity", "UNSPECIFIED")
                        severity_counts[severity] = severity_counts.get(severity, 0) + 1
                        if properties.get("fixed_version") not in (
                            None,
                            "not fixed",
                            "",
                        ):
                            fixable += 1
                entry.update(
                    status="SCANNED",
                    findings=len(results),
                    sarif_levels=levels,
                    severity_counts=severity_counts,
                    rules_with_known_fix=fixable,
                )
                print(f"{image}: {len(results)} findings", flush=True)
        except (subprocess.TimeoutExpired, ValueError, OSError) as error:
            entry.update(status="SCAN_FAILED", reason=type(error).__name__)
            failed = True
        report["images"].append(entry)
        (ROOT / "docs/image-scan-summary.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    if failed:
        raise SystemExit("Some scans failed; inspect docs/image-scan-summary.json")
    print(
        "All runtime images scanned; findings require review, not an automatic safety claim"
    )


if __name__ == "__main__":
    main()

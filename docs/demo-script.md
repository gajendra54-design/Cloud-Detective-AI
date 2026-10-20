# Reproducible demonstration

Allow several minutes for the detector and historical metric windows. Use only the disposable local stack.

1. From the project directory run `docker compose up --build -d --wait`. Open http://localhost:5173 and confirm the service observations load. Idle request metrics may be unavailable; do not describe them as zero traffic errors.
2. Open the local operator controls. Enter the investigator and approver values from your local `.env` privately. Never include them in screenshots or recordings.
3. In Demo lab send test traffic while healthy. Inspect Overview and Grafana at http://localhost:3000 to explain the observed metrics.
4. Activate the bounded errors scenario and send test traffic. Wait for sustained observations to create an incident, then open it. Explain the rule, timestamp and affected service.
5. Select Investigate. Expand cited evidence and show its source and timestamp. Explain that deterministic-mock is the default and that confidence is not proof of causality.
6. Propose recovery. Review the exact target, scenario revision, expiry and verification plan. Approve the exact action, then execute it. Show the recorded fresh request results and resolved state only if verification passes.
7. Show the audit history and timeline. Explain that submitting the same execution again returns its recorded result.
8. Demonstrate the failed-recovery branch using `.venv\Scripts\python.exe scripts/verify_lifecycle.py` (Linux: `.venv/bin/python scripts/verify_lifecycle.py`). It temporarily breaks payment, proves that checkout remediation alone fails verification, then restores services and verifies a new successful action. Inspect its actual report in `docs/live-verification.json`.
9. Finish by showing the acceptance checklist. State that real restart/rollback, individual-user authentication, live-model validation and remote CI remain incomplete.

The automated script can reuse a detected open incident. It does not create a fake incident directly in the database. Do not repeatedly activate scenarios merely because the detector needs its persistence window. Stop the controlled scenario from Demo lab if ending early; scenarios also expire automatically.

For a recording, capture the dashboard and evidence only, close credential fields, and narrate observed results. This guide is a recording plan; no demo video has been produced.

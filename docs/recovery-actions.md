# Controlled recovery actions

All actions require an open investigated incident, a proposal, approver authorization and explicit execution. Approval binds the exact target, parameters and incident version. Reject a pending proposal before selecting a different action.

## Restart disposable service

Select **Restart disposable service** in the incident drawer before proposing. The target advertises a process boot ID and restart capability. The proposal binds both this ID and the scenario revision. A stale process, changed scenario or repeated target request is rejected.

The authenticated demo endpoint can only schedule exit code 75 in its own process. It accepts no command, path, image, service selector or arbitrary argument. Compose uses `on-failure:3` to restart that same container. The backend has no Docker socket and no shell execution adapter. This follows [Docker's documented restart policy](https://docs.docker.com/engine/containers/start-containers-automatically/).

The first ten seconds after process startup block restart requests. Once claimed, subsequent scenario changes and restarts are blocked until the process exits. The backend waits for a distinct boot ID and then runs independent business-request, readiness, dependency, latency and metrics-delta verification. A returned 202 or changed boot ID alone never resolves an incident. An ambiguous timeout remains failed rather than retrying an unsafe operation.

Impact: brief downtime and loss of this disposable process's in-memory orders, logs, traces, failure state and counters. PostgreSQL incident/evidence/audit history remains. Restart cannot fix a broken downstream dependency; failed verification leaves the incident open. This is a cooperative restart: an unreachable/hung demo cannot accept the control request and requires manual local operator intervention.

## Roll back bundled demo release

Activate the deployment scenario. It selects the bundled `demo-v2` regression behavior and records `demo-v1` as the previous version. Investigate, select **Roll back bundled demo release**, then propose, approve and execute.

Rollback accepts only demo-v2 to its recorded demo-v1 predecessor, with the exact scenario revision. It restores the stable bundled request behavior and emits a release rollback event. The original regression, previous version and rollback result are retained in investigation evidence and the action result. Scenario expiry or another change invalidates the rollback precondition.

This is an in-process rollback between fixed bundled demo behaviors, not a container-image deployment rollback. It does not fetch code, switch an arbitrary image or modify real infrastructure. Image-tag rollout, deployment orchestration and durable release catalogs remain future work.

## Existing actions

Restore scenario / verify health keeps the original automatic selection: disable_failure for an active scenario, health_check for a healthy target. These have the same approval, replay and verification requirements.

## Reproduce

Run `.venv\Scripts\python.exe scripts/verify_recovery_actions.py` on Windows (Linux: `.venv/bin/python scripts/verify_recovery_actions.py`). It waits for real detection, verifies unapproved execution is blocked, approves each action, checks recovery and replays execution. It restores healthy mode and records actual results in `docs/recovery-actions-verification.json`. Detection cooldowns may make it take two minutes. Use the existing default legacy credentials for this script.

# Verification report — 2026-10-18

## Executed successfully

- Python: 34 tests passed. Coverage includes migrations, service failures/expiry, real trace IDs, detection persistence/reset/deduplication, telemetry outage, structured findings, citation rejection, fallback, role separation, approval fingerprint/expiry, scenario revision changes, failed recovery, successful recovery, health-check actions, execution replay and failed-auth rate limiting.
- Ruff lint and formatting passed. `pip check` found no broken requirements.
- React/TypeScript production build and ESLint passed. Charts are split into a separate bundle.
- Python package audit: initial audit found vulnerabilities in old Starlette/pytest; dependencies were upgraded. The resulting locked-environment audit reported no known vulnerabilities. Machine-readable result: dependency-audit.json.
- npm install audit reported zero vulnerabilities after adding frontend dependencies and lint tooling.
- Docker Compose built and started all seven services. PostgreSQL migrations applied through 0003.
- verify_stage1.py passed all implemented scenarios, expiry, authorization rejection, PostgreSQL inventory, real metrics and two Prometheus targets.
- verify_lifecycle.py passed real detection/evidence/approval flow, deliberately failed dependency recovery, successful recovery, and idempotent execution replay. See live-verification.json for IDs and actual samples.
- verify_observability.py proved checkout and payment share one OpenTelemetry trace and Grafana has four provisioned panels. See observability-verification.json.
- Approved health-check actions independently verified and resolved the two remaining demo alerts without changing their healthy scenarios.
- Source scan found none of the actual local secret values in publishable project text.
- Browser citation clicks expanded the correct evidence record; Escape closed the dialog and restored focus. Actual screenshots are in screenshots/overview.png, screenshots/investigation.png and screenshots/evidence.png.
- Browser inspection confirmed real incident data, a resolved incident, evidence citations, both failed and successful recovery results, and timeline entries.

The successful live recovery observed three HTTP 201 responses, zero new errors, ready dependencies and approximately 15–21 ms request durations. These are one local run's measurements, not a benchmark or production SLO claim.

## Environment issues resolved

Docker and package access required approved local/network permissions. First-time image downloads were slow. The first frontend container npm install failed; cached downloads and longer registry timeouts allowed the retry to pass. Runtime-only Python dependency locking reduced image tooling. A Windows timing test uses a small scheduling tolerance for the 300 ms simulated delay.

## Remaining verification limits

One upstream Starlette deprecation warning recommends httpx2 for its test client; current tests pass with the supported compatibility path. A live Ollama response, remote GitHub Actions execution, container-image CVE scans, multi-worker load/fault tests, long-duration recovery/SLO windows, full keyboard/screen-reader audits and second-machine setup are not verified. No production deployment is claimed.


## History reliability increment — 2026-10-19

36 Python tests passed in 5.22 seconds, including new regression checks for evidence and timeline overflow, identical timestamps, bounded page sizes, cursor exhaustion and incident-scoped evidence lookup. The existing upstream Starlette warning remains. Ruff checks and frontend TypeScript, production build and ESLint passed. The initial sandboxed test process stalled; the successful run used approved local socket access.

The new documentation includes a reproducible demonstration, architecture decisions and 32 interview questions. No live model, production identity, remote CI or restart/rollback completion is implied.

The backend and frontend Docker images rebuilt successfully and Compose reported both healthy. Browser inspection of the rebuilt dashboard confirmed the persisted investigation, seven evidence records, both recovery outcomes and complete timeline render. Screenshot: screenshots/history-update.png. Overflow pagination is covered by API regression tests; browser overflow controls were not exercised against synthetic production data.


## Named local accounts — 2026-10-19

- 41 tests passed in 25.21 seconds with one existing Starlette compatibility warning.
- Ruff and frontend TypeScript/build/ESLint passed.
- Compose rebuilt the backend and frontend successfully; migration 0004 applied and both services reported healthy.
- Live `docker compose exec -T backend python verify_accounts.py` passed for viewer, investigator and approver: sign-in, role enforcement, logout revocation and individual audit attribution. It used real HTTP and PostgreSQL and disabled all temporary test users afterward.
- The browser sign-in form is provided; live authentication was verified through HTTP. No permanent user passwords were generated or exposed by the agent. Use docs/accounts.md to provision your own named accounts privately.


## Recovery actions — 2026-10-19

49 Python tests passed in 30.14 seconds with the existing upstream compatibility warning. Ruff and frontend lint/build passed. The rebuilt backend, frontend, checkout and payment all passed Compose health checks. The live restart check observed a changed boot identity and independently successful recovery; replay returned the recorded result. Full results are recorded in recovery-actions-verification.json after both actions finish. The rollback is between bundled demo behaviors, not container images.


Both live actions passed: restart_service and rollback_demo, each with independent verification and replay checks. Report: recovery-actions-verification.json. Browser inspection confirmed the rollback action succeeded, demo-v1 was restored, three requests returned HTTP 201, no new errors were measured, and the incident resolved. Both demo services are healthy and there are no open incidents after this run. Screenshot: screenshots/recovery-actions.png.


## AI and container scans — 2026-10-19

52 tests passed in 38.38 seconds with the existing Starlette compatibility warning; Ruff passed. The installed qwen2.5:7b-instruct model returned valid structured findings and supplied citations in 115.45 seconds. Manual interpretation review identified unsupported claims, documented in ai-validation.md. This is a live integration pass, not a factual-accuracy pass.

Docker Scout scanned all seven runtime images and found vulnerabilities. Reports are in image-scans/ and image-scan-summary.json. The Python Dockerfiles now pin pip 26.2.1; rebuilt services passed health checks. Afterward verify_observability.py passed real cross-service tracing and the four-panel Grafana dashboard. See container-security.md for unresolved findings; the project has not passed a production security clearance.

Final installer-removal rescan: backend/checkout/payment each have 28 remaining OS findings and no PyPI findings, down from 34 total initially. Other image findings remain unresolved. Final rebuilt containers passed Compose health checks and the live trace/Grafana verification passed again.

AI guardrail increment: 55 tests passed in 41.72 seconds with the existing Starlette warning. Ruff passed. The live local model returned ollama-guarded in 60.62 seconds; retained summary explicitly preserved unavailable metrics and not-ready state, recovery checks and abort rules matched deterministic policy, and confidence was capped. Original unguarded output is preserved for comparison.

Concurrent recovery increment: 55 tests passed in 32.40 seconds; Ruff passed and Compose reported the rebuilt backend healthy. verify_concurrency.py passed eight-way simultaneous proposal, approval and execution bursts against real PostgreSQL, requiring one action, one approval, one execution and three fresh verification requests. The test restored healthy mode. Results: concurrency-verification.json. This tests one backend process, not multi-worker crash/load behavior.

## Runtime upgrade verification — 2026-10-19

Nginx 1.30.6, Prometheus 3.13.4 and Grafana 13.2.4 are running; PostgreSQL is pinned to the already-used 17.11. Backups were saved locally before replacement and Grafana database/plugins migrated to persistent storage. Frontend build/HTTP access, verify_stage1.py, verify_lifecycle.py and verify_observability.py passed. The first stage1 run occurred before initial Prometheus scrapes; a bounded target-readiness wait was added and its rerun passed. Ruff check/format passed. All seven runtime image scans completed; results and remaining vulnerabilities are documented in container-security.md and image-scan-summary.json.

Frontend package remediation: updated zlib and removed unused curl/libcurl from the runtime, restoring USER 101 after build-time package operations. Frontend build, page/static asset requests, proxied backend readiness, nginx configuration validation and non-root identity checks passed. Frontend Scout findings decreased from 36 to 11; remaining libxml2 findings are unresolved. See container-security.md and the current scan summary.

Unused Nginx module removal: dependency/configuration inspection established that the dashboard does not load the optional XSLT or njs modules. Removing them also removed libxml2. Frontend build, HTTP/static assets/API proxy, nginx -t, UID 101 and package-absence checks passed. The rebuilt frontend has zero findings in its current Docker Scout scan; other images retain unresolved findings. See image-scan-summary.json for the exact image identity.

PostgreSQL package patch: derived image retains PostgreSQL 17.11 and upgrades zlib to 1.3.2-r1. Fresh local backup taken, pgdata retained, database health passed. Full live lifecycle passed including failure handling, verified recovery, replay and audit persistence. All image scans completed: PostgreSQL 72 to 71 findings; frontend remains zero. Scanner lint/format passed. Required XML and upstream gosu dependencies remain unresolved.

Database outage reliability increment: initial live checks exposed blocked readiness during PostgreSQL downtime. Synchronous monitor database work now runs off the event loop; connections are bounded and readiness shares a two-second probe wait. The live stop/start test passed readiness 503, liveness 200, retained record IDs, no backend restart and resumed telemetry. 56 regression tests passed in 32.62 seconds; Ruff passed. Report: database-restart-verification.json. This is graceful single-node outage evidence, not crash/distributed consistency certification.

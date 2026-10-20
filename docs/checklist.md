# Acceptance checklist — 2026-10-18

These results describe the implemented local core. They do not claim every feature in the larger master specification is complete.

1. PASS — local Compose stack builds/starts, including PostgreSQL, backend, checkout, payment, frontend, Prometheus and Grafana.
2. PASS — real health endpoints, counters, latency histograms, process metrics and cross-service OpenTelemetry traces verified.
3. PASS — every implemented bounded failure mode and deactivation/expiry verified against live services.
4. PASS — actual polling detects readiness/error incidents; the live lifecycle script uses detected records.
5. PASS — React dashboard displays database incidents and observed telemetry; verified in browser.
6. PASS — evidence snapshots retain source, timestamp and stable IDs; trace correlation verified across services.
7. PASS — deterministic diagnosis works with no LLM.
8. PASS for schema/citation enforcement — validated findings and unknown-citation/extra-field rejection tested. PASS for a live Ollama schema/citation response; factual interpretation review found errors (see ai-validation.md).
9. PASS — missing Prometheus telemetry is explicit and tested; no fabricated zeros.
10. PASS — only disable_failure, health_check, restart_service and rollback_demo actions are exposed; no arbitrary commands.
11. PASS for local role authorization — investigator cannot approve; unauthorized attempts are audited/rate-limited. Named local users and revocable sessions are implemented; production identity remains unfinished.
12. PASS for tested replay — duplicate execution reads its existing result. SQL conditional claims enforce the execution boundary; eight-way concurrent HTTP proposal/approval/execution testing passed on PostgreSQL; multi-process load testing remains outstanding.
13. PASS — proposals, approvals, execution, verification and denied authorization are audited; both live outcomes persisted.
14. PASS — fresh business requests, health, dependency readiness, latency and metrics deltas determine recovery.
15. PASS — live payment failure caused verification failure while the checkout control command succeeded; incident stayed OPEN.
16. PASS — 55 Python tests and repeatable live success/failure scripts; frontend lint/type/build checks pass.
17. NOT YET TESTED remotely — GitHub Actions workflow includes Python/frontend checks, audits, Compose and live verification; no GitHub repository has been published.
18. PASS — setup, configuration, troubleshooting, runbooks, API, architecture and demonstration documentation written.
19. PASS for implemented boundaries — no unrestricted host execution API, privileged container or host Docker socket. Secrets remain in ignored .env. All runtime images have been scanned; unresolved vulnerabilities remain (see container-security.md).
20. PASS locally — scripts reproduce detection, investigation, failed recovery, successful recovery and execution replay. A clean second-machine reproduction is NOT YET TESTED.

## Stage progress

- Stage 0: complete for the local project.
- Stage 1: working services, persistence, containers, bounded failures, metrics and bounded tracing verified.
- Stage 2: core detection, deduplication, telemetry history, React dashboard and Grafana provisioning implemented and locally verified. More sophisticated deployment-correlated alert rules remain future work.
- Stage 3: deterministic diagnosis, evidence collection, provider schema/fallback and Ollama adapter implemented. Live-model schema/citation validation passed; factual consistency improvements remain.
- Stage 4: disable_failure and health_check approval/verification implemented and tested. Controlled container process restart and recorded bundled demo-release rollback are implemented; container-image rollback is not.
- Stage 5: local role authorization, failed-auth limiting, audit, dependency upgrades/scans and CI implemented. Named local users, session revocation and CLI administration are implemented. Production identity, web administration, load testing and image scans remain.
- Stage 6: documentation, demonstration scripts and interview/portfolio guide written. Screenshots are captured from the actual application; a demo video and remote publication are not produced.


## Continuation — 2026-10-19

- Added stable cursor pagination for evidence/timeline history, incident-scoped evidence retrieval and dashboard older-history controls. Regression tests cover both page limits and identical timestamps.
- Added `demo-script.md`, `decisions/architecture-decisions.md` and `interview-guide.md` with 32 implementation-specific answers.
- Python suite: 36 passed; frontend TypeScript/build/ESLint and Python Ruff checks passed. Live container rebuild verification is recorded separately in verification.md.
- Full master-spec completion is still pending the Stage 3–6 limitations above; these changes do not implement production identity or restart/rollback.


## Named accounts — 2026-10-19

- Added migration 0004, local named users, three roles, salted scrypt password hashes, 30-minute hashed bearer sessions, login/logout and CLI account administration.
- Account changes revoke sessions; actions and approvals record individual user IDs. Shared legacy credentials can be disabled explicitly.
- 55 Python tests pass, including expiry, disabled accounts, role separation, login throttling and secret-redacted validation.
- Dashboard sign-in and sign-out are implemented. No production authentication claim: loopback read APIs remain public and TLS/MFA/external identity/distributed limits are absent.


## Recovery action increment — 2026-10-19

- Added approved self-restart of disposable containers with Docker on-failure policy, exact boot/revision preconditions, new-process proof and independent verification.
- Added recorded demo-v2 to demo-v1 bundled-behavior rollback. Container-image rollback is still outside this implementation.
- 55 Python tests pass, including failed verification, stale/duplicate requests, unsupported targets, release restrictions and role protection. Frontend build/lint and Ruff pass.
- Live restart and bundled-release rollback both passed; actual results are recorded in recovery-actions-verification.json. Remaining work includes real-model validation, image vulnerability scanning, broader fault/load testing and remote CI.


## AI and image scanning — 2026-10-19

- Tested installed qwen2.5:7b-instruct with retained real incident evidence: schema and citations passed in 115.45 seconds. Interpretation review found unsupported statements; default mock/rules mode remains unchanged.
- Hardened citation validation to the actual transmitted evidence set and added bounded configurable AI timeouts.
- 55 Python tests pass, with Ruff checks passing.
- Scanned all seven runtime images and retained SARIF reports/image IDs. Scan findings are unresolved; scanning is complete but security remediation is not.
- Used updated pip for installation, removed it from the three Python runtime images, and rebuilt healthy containers. Final scans show 28 OS findings per Python image and no PyPI findings. Live trace/Grafana verification passed after the rebuild.


## Guarded AI explanations — 2026-10-19

- Authoritative factual summary and recovery policy now come from deterministic evidence rules. Model hypotheses are explicitly unverified and confidence is capped.
- 55 tests passed; live local-model retest passed schema, citation and factual-summary/recovery guardrails in 60.62 seconds.
- This does not establish correctness of every free-text hypothesis. Container vulnerability remediation, broader reliability testing, image rollback and remote CI remain unfinished.


## Concurrent recovery requests — 2026-10-19

- Added per-incident PostgreSQL proposal locking and a transaction-time incident/version recheck.
- Live eight-request bursts passed for proposal, approval and execution: one proposal, one accepted approval, one execution and three fresh verification requests.
- 55 regression tests passed; Ruff passed and the rebuilt backend is healthy. Actual live results: concurrency-verification.json.
- Single-backend concurrent-request evidence does not establish distributed correctness, sustained capacity or crash consistency. No user intervention was needed for this increment.

## Runtime security updates — 2026-10-19

- Updated Nginx, Prometheus and Grafana; pinned PostgreSQL 17.11. Preserved database data and migrated Grafana settings/plugins into a persistent volume after backup.
- Build, local demo scenarios, full recovery lifecycle and trace/Grafana integration checks passed.
- Rescanned all seven images: frontend 165 to 36 findings, Prometheus 128 to 31, Grafana 263 to 93. Other images retain their previous counts. High/critical and fixable findings remain; security remediation is incomplete.
- Remaining broader work includes package-level security triage, distributed/crash/load tests, actual container-image rollback and remote CI verification. No manual user setup was needed for this increment.

Frontend package remediation: zlib updated and unused curl removed; rebuilt frontend passed HTTP/static assets/API proxy/configuration/non-root checks. Findings decreased from 36 to 11. Remaining frontend libxml2 and other container findings still require follow-up.

Frontend image scan: zero findings after removing unused XSLT/njs modules and their XML dependencies. Build and runtime checks passed. This completes the currently reported frontend image findings only; other container security work and broader reliability/remote CI checks remain unfinished.

PostgreSQL OS patch: backup and persistent-volume-preserving replacement completed; PostgreSQL remains 17.11 with patched zlib. Live lifecycle and health checks passed. Image findings decreased from 72 to 71. Remaining database/observability/base-image findings, broader reliability tests and remote CI remain unfinished.

Database outage recovery: fixed blocking readiness/monitor behavior and added a repeatable local/CI stop-start check. Live test and 56 regression tests passed. Existing records survived and monitoring resumed without backend restart. Broader crash/load/multi-worker tests and remote CI execution remain pending.

# Reliability testing

## Concurrent recovery requests

Run `.venv\Scripts\python.exe scripts/verify_concurrency.py` from the project directory (Linux: `.venv/bin/python scripts/verify_concurrency.py`). The local stack must be healthy with legacy test credentials enabled. This bounded test changes only the disposable checkout scenario and restores healthy mode in a finally block.

The script waits for a real detected readiness incident, investigates it, then releases eight concurrent HTTP requests for each stage: proposal, approval and execution. It requires one unique proposal ID, exactly one successful approval, one execution timeline entry, one verification completion, three fresh verification requests and a resolved incident. Repeated execution must read the same result. Results are saved to concurrency-verification.json only if all assertions pass.

PostgreSQL row locking serializes proposal creation per incident. The transaction rechecks incident status/version after collecting upstream preconditions. Approval and execution retain conditional SQL state transitions. This prevents one class of duplicate work; it is not a universal exactly-once guarantee across external-system failures.

## Scope and remaining work

The live test uses real PostgreSQL and concurrent HTTP connections to one backend process. It does not establish multi-worker/distributed correctness, sustained-load capacity, crash consistency or long-duration recovery guarantees. Those remain separate tests. SQLite unit tests do not validate PostgreSQL row-lock semantics.

Existing lifecycle verification covers failed dependency recovery, success and execution replay. Recovery-action verification covers process identity change on restart and recorded demo-release rollback. The standard suite covers authorization, stale revisions, expiry, session revocation, missing telemetry and AI validation.

CI includes the concurrency script. Remote GitHub Actions execution remains unverified until the project is published and the workflow runs there.

## Database outage recovery — 2026-10-19

Added scripts/verify_database_restart.py and included it in the CI workflow. It briefly stops PostgreSQL, checks readiness 503 and liveness 200, restores the database in a finally block, verifies pre-existing incident/timeline/audit/user IDs remain, checks fresh telemetry writes, and verifies the backend container/start time did not change. It saves docs/database-restart-verification.json. This intentionally interrupts the local database and should be run only against this disposable local stack.

The first live run exposed readiness hanging during a database outage. A connection timeout alone did not fix it. Monitoring now executes synchronous database transactions in a worker thread, leaving the server event loop responsive. PostgreSQL connections have a three-second connection timeout. Readiness uses a shared outstanding background probe with a two-second response timeout, avoiding a new probe thread for each request while DNS/database connection work is slow.

The final local outage run passed: 11 incident IDs, 77 timeline IDs, 94 audit IDs and 3 user IDs remained present, the backend did not restart, and monitoring resumed. This checks record identity retention, not byte-for-byte content equality. It covers a graceful single-node stop/start; abrupt disk failure, mid-remediation process crashes, sustained load and distributed failover remain unverified. Remote CI is configured but has not been run remotely.

56 Python tests passed in 32.62 seconds, including a concurrent blocked-probe regression test. Ruff lint and formatting passed. The existing upstream Starlette/httpx deprecation warning remains. Existing image scans refer to their recorded image identities; the rebuilt backend's application source changed after that scan.

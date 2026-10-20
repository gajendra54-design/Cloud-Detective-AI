# Incident runbooks

## Error/readiness incident

Activate `errors` for 60 seconds and send test traffic. Expect checkout 503, readiness 503 and a persistent incident after two polls. Investigate and inspect the scenario evidence alongside observed metrics. Propose disabling the active revision; review, approve, execute and inspect all verification samples. If a dependency remains unhealthy, the result must be FAILED and the incident must stay OPEN.

## Latency incident

Activate `latency`, send multiple batches of five requests, then wait for two Prometheus observations. The injected delay is approximately 300 ms; histogram p95 is a bucket interpolation, not exact per-request timing. A rate rule requires at least three observed requests. Follow the same approval path. Verification latency must be below 250 ms by default.

## Dependency outage / failed recovery

Use `scripts/verify_lifecycle.py` for a reproducible two-service failure. It activates a payment failure after checkout recovery has been approved. Disabling the checkout failure cannot repair payment; verification therefore fails. The script restores payment, creates a new revision-bound proposal, verifies recovery, and asserts replay does not execute again.

## No active scenario

The scenario may have expired. A high historical error rate alone does not justify changing a healthy demo. The proposal will offer `health_check`, which sends three predefined business requests and independently verifies health/latency/counters. Explicit approval is still required before it can resolve the incident. A failed check preserves the open incident.

## Missing telemetry

If Prometheus is down, evidence shows missing metric fields. Health-based detection can continue; rate-based diagnosis cannot infer zero errors. Restore monitoring and investigate again. If verification cannot read fresh counters, it fails safely.

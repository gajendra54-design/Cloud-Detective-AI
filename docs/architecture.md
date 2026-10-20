# Architecture

The React/TypeScript dashboard is served by unprivileged Nginx, which proxies its same-origin `/api` requests to FastAPI. The platform API and its background monitor share PostgreSQL. The checkout demo calls the payment demo over the internal Compose network. Prometheus scrapes both every five seconds; Grafana and the detector use those observations.

## Incident lifecycle

The monitor queries a fixed allowlist of PromQL expressions and internal health targets. Two consecutive observations are required to create an incident. Readiness/unavailability rules do not need business traffic; error-rate and p95 rules require at least three estimated requests in the one-minute window. Telemetry samples retain one hour of dashboard history. Incidents/evidence persist until the operator manages the database; no destructive cleanup API exists.

A nullable unique open key (`service:rule`) prevents duplicate open incidents. A PostgreSQL advisory transaction lock serializes detector writes across workers. The process polls serially by default. Historical evidence is copied into incident records with stable IDs and UTC timestamps. Missing metrics are null/unavailable rather than zero. A recent resolved event suppresses re-alerting for 75 seconds.

Investigation collects a fresh observation, scenario revision, bounded structured logs, spans and change events. The deterministic rules explain the active scenario as a hypothesis; the optional Ollama adapter sees only sanitized observations and scenario state. Pydantic rejects extra fields, unexpected actions, invalid confidence values and unknown evidence citations. Neither provider can execute infrastructure changes.

The operator proposes `disable_failure` against an active recorded revision, or `health_check` when the scenario is already healthy. Approval binds the exact action, target, parameters and incident version through a fingerprint. Compare-and-set database updates claim approval and execution. A duplicate execution returns stored state rather than running again. The demo also checks the expected revision, protecting against concurrent scenario changes. Five-minute proposal expiry and a 20-second execution limit bound the workflow. Abandoned executions become failed/inconclusive after expiry and do not resolve incidents.

Verification sends three independent business requests and checks readiness, payment readiness for checkout, latency and fresh request/error counter deltas. Results and operator transitions are audited. Historical Prometheus windows are deliberately not used as immediate proof of recovery. A short demo observation is weaker than a production SLO window.

## Tracing

Each demo service has an OpenTelemetry SDK provider and FastAPI/HTTPX instrumentation. W3C trace context propagates from checkout to payment. A custom exporter retains only 100 recent span summaries with an attribute allowlist; no headers, bodies or raw URLs are exported. Request logs retain 100 generated records; change events retain 30 records. The authenticated evidence endpoint exposes these bounded summaries. They are ephemeral until copied to PostgreSQL incident evidence. An external collector/trace store is not yet configured.

## Modules

- `backend/app/api`: read APIs and lifecycle transitions.
- `backend/app/services`: telemetry, detection, investigation and recovery.
- `backend/app/workers`: polling, retention and action-expiry handling.
- `backend/app/db.py`: ORM models; `backend/migrations`: versioned schema.
- `demo-services`: demo behavior and tracing.
- `frontend/src`: API types, dashboard, charts and incident drawer.
- `observability`: Prometheus and provisioned Grafana configuration.
- `scripts`: environment bootstrap and repeatable live verification.

## References used

[OpenTelemetry Python instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/), [Prometheus query API](https://github.com/prometheus/prometheus/blob/main/docs/querying/api.md), [Ollama structured outputs](https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx).


### Model explanation boundary

Validated model output passes through a grounding step before persistence: summary and recovery policy are regenerated from deterministic evidence rules, model causes are labeled unverified, and confidence is capped. This complements schema/citation checks and limits unsupported model statements in authoritative fields. It does not validate all free-text hypotheses. See ai-validation.md.

# Architecture decisions

## Local Compose first

Use a disposable two-service environment, PostgreSQL, Prometheus and Grafana to demonstrate actual failures without cloud credentials. Cloud hosting and Kubernetes are optional later work. This sacrifices production scale for reproducibility and small operational scope.

## Deterministic diagnosis with an optional model

Rules remain available offline. The Ollama adapter enriches explanations only after strict schema and citation validation; failures fall back to rules. Model output never grants permissions or runs commands. A live provider response is still unverified.

## Human approval and conditional execution

Bind approval to exact action parameters, target, scenario revision and incident version. Conditional SQL transitions limit duplicate claims; independent verification determines resolution. Only disable_failure and health_check exist today. A Docker socket is deliberately absent; adding real restart needs a narrowly scoped execution boundary.

## Bounded evidence with stable retrieval

Keep bounded in-memory telemetry buffers and persist investigation snapshots. Return recent evidence and timeline pages, ordered by timestamp and ID; an exclusive before-ID cursor retrieves earlier pages without offset shifts from new records. Retrieve individual cited evidence through an incident-scoped endpoint. This supports older citations without unbounded list responses. Persistent evidence retention policies remain future work.

## Local role credentials

Distinct investigator/approver bearer tokens enable backend role separation in the demo. They do not represent individual users; production mode is refused. Future identity integration must add individual audit attribution, sessions and administrative lifecycle controls.

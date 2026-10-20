# Technical interview guide

Use these answers to explain the implementation honestly. The two-minute introduction is in [portfolio.md](portfolio.md).

## 1. Why build this project?

An alert alone does not explain a failure or prove recovery. This project connects detection, retained evidence, diagnosis, human approval and fresh recovery checks so a reviewer can follow the entire decision.

## 2. Walk through the architecture.

Checkout calls payment. Prometheus scrapes their metrics; a backend worker combines metrics and health checks to create PostgreSQL incidents. React reads the backend API, while Grafana presents monitoring panels. Investigation and approved recovery run through separate backend services.

## 3. Why Prometheus?

It collects numerical time series and supports rate and percentile queries. The application uses fixed queries rather than accepting arbitrary query text from a user. Missing results remain unavailable instead of becoming zero.

## 4. Why Grafana as well as React?

Grafana is useful for operational metric panels. React provides incident-specific evidence, approval and verification workflows that are not ordinary monitoring charts.

## 5. How do metrics, logs and traces differ?

Metrics describe aggregate behavior, logs capture individual events, and traces connect work across services. Here, an error-rate signal can lead to request logs and correlated checkout/payment spans.

## 6. How are traces correlated?

OpenTelemetry instruments incoming FastAPI and outgoing HTTPX calls. Context travels with the dependency request, allowing checkout and payment spans to share a trace ID. The live observability script verifies this relationship.

## 7. Where are traces stored?

Each demo keeps a bounded in-memory span buffer, and investigation persists selected snapshots. This is not a durable distributed tracing platform; a collector and trace store remain future work.

## 8. How does Docker networking work here?

Containers address one another by Compose service name. Published dashboard/API ports bind to loopback. Payment and PostgreSQL do not need public host ports for the application to reach them.

## 9. How are failure scenarios constrained?

Only named scenarios are accepted, with bounded duration and resource use. CPU and memory pressure are deliberately limited, and the control API requires a secret. There is no arbitrary shell command endpoint.

## 10. How does detection reduce noise?

Conditions must persist across configured polls. An open incident key deduplicates each service/rule pair, and a short cooldown after resolution reduces immediate repeated alerts from historical metric windows.

## 11. Does a quiet alert resolve an incident?

No. The worker does not resolve incidents merely because a threshold clears. An approved recovery or health-check procedure must meet independent verification criteria.

## 12. Is diagnosis the same as root-cause proof?

No. A detected symptom and a coincident controlled scenario support a hypothesis. Findings retain alternative explanations, evidence strength and uncertainty rather than claiming production causality.

## 13. Why keep deterministic diagnosis?

It works offline and gives reproducible behavior in tests. It also provides a fallback when the optional model is unavailable or returns invalid findings.

## 14. What does the model adapter do?

It sends a bounded structured evidence payload to the configured Ollama chat endpoint and validates a structured response. Provider selection is configurable. An actual local model response remains unverified on this machine.

## 15. How do you handle hallucinated citations?

Every cited evidence ID must occur in the supplied set. Unknown IDs and unexpected output fields fail validation and trigger fallback. Valid citations alone still do not guarantee a correct interpretation.

## 16. How do you handle prompt injection in telemetry?

Telemetry is untrusted data, not permission. The provider receives selected sanitized fields, and its schema cannot introduce executable commands. Backend authorization and action selection do not depend on instructions in logs.

## 17. What prevents secrets reaching the model?

Sanitization removes sensitive fields and redacts recognizable bearer tokens and email addresses. Payloads and excerpts are bounded. This reduces exposure but is not a universal guarantee against every possible sensitive string.

## 18. How does approval bind to an action?

A fingerprint covers the action, target, parameters and incident version. Approval must match it, remain unexpired, and refer to an open incident. Scenario revision checks prevent acting on a changed failure configuration.

## 19. Which recovery actions exist?

Disable a controlled failure and run a predefined health check are implemented. Real container restart and rollback to a recorded deployment are not implemented and should not be demonstrated as available.

## 20. How does backend authorization work?

Named local users sign in for revocable 30-minute sessions. The backend enforces each user role and records stable user IDs on protected actions. Optional legacy shared-role tokens remain for demo compatibility. This is local authentication; production identity integration remains unfinished.

## 21. How do you prevent repeated execution?

A conditional database transition claims an approved action once. Replayed requests return the existing execution state or result. This prevents ordinary duplicate submissions; multi-process fault and load tests remain outstanding.

## 22. What happens if the worker crashes during recovery?

The system must not assume success. Stale executing or verifying actions eventually become failed/inconclusive, leaving the incident unresolved. Production adapters would also need external action reconciliation.

## 23. How is recovery proven?

Fresh business requests must succeed, readiness and dependencies must be healthy, latency must be below the threshold, and independent metrics must show new requests without new errors. The current three-request window is a local demonstration, not long-term SLO proof.

## 24. Why not immediately use the Prometheus error rate?

Its rolling window can still contain pre-action failures. Fresh metric counter deltas and business requests test the post-action period. A sustained production verification window would add longer observation.

## 25. Can a successful action still fail recovery?

Yes. Disabling checkout failure can succeed while payment remains broken. The live lifecycle test deliberately exercises this case and checks that the incident stays open.

## 26. What is persisted in PostgreSQL?

Services, incidents, evidence, timeline entries, investigations, remediation state and audit events persist. Alembic manages schema changes. Some detailed approval/execution data lives on the remediation record rather than separate normalized tables.

## 27. Is audit history immutable?

Ordinary API users cannot update or delete audit records. Database administrators can still modify storage; tamper-resistant external audit retention is not implemented.

## 28. How do old evidence links remain usable?

Evidence has stable IDs and an incident-scoped detail endpoint. History uses bounded cursor pages, and the drawer retrieves cited records even outside the current page. IDs from a different incident return 404.

## 29. What does CI validate?

The workflow runs Python tests and lint, frontend type/build/lint checks, package audits and live Compose verification scripts. These checks have local evidence; the workflow has not yet run on a published GitHub repository.

## 30. How would you debug unavailable telemetry?

Check the service health and metrics endpoint, Prometheus target status and backend query errors. Verify container DNS and configuration. Preserve unavailable status until evidence exists instead of replacing missing measurements with healthy values.

## 31. How would you scale this system?

Separate collection and execution workers, define durable job ownership and retry/reconciliation rules, add individual identity and quotas, and introduce durable trace storage. Validate concurrency and retention against measured workloads before claiming scalability.

## 32. What are the biggest remaining limitations?

Production identity, restart/rollback adapters, live-model validation, image scanning, remote CI and longer fault/load testing remain unfinished. Named local users and revocable sessions are now implemented. The portfolio claim is a working local incident lifecycle, not a production-ready autonomous operator.

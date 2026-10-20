# Portfolio and interview guide

## Short description

Cloud Detective AI is a local SRE incident investigation platform that connects real demo telemetry to persistent incidents, evidence-grounded diagnosis, human-approved remediation and independent recovery verification. It combines FastAPI, PostgreSQL, React, Docker Compose, Prometheus, Grafana and OpenTelemetry, with deterministic analysis and an optional schema-validated local LLM adapter.

## Two-minute presentation

“I built Cloud Detective AI to demonstrate the complete incident lifecycle. A small checkout service calls a payment service and emits metrics, logs and correlated traces. I can activate bounded failures without touching production infrastructure.

The detector evaluates real health and Prometheus observations. It waits for sustained conditions, deduplicates open incidents and stores timestamped evidence. The dashboard shows actual measurements and makes missing data explicit.

Investigation starts with deterministic rules. An optional local model can enrich the explanation, but its response must match a schema and cite existing evidence. It cannot execute commands.

The recovery boundary is the most important part: an operator reviews a proposal bound to an exact scenario revision and incident version. Approval and execution are conditional database transitions. Replays cannot cause another execution. After the action, three fresh requests and independent health, latency and counter checks decide whether recovery succeeded.

The demo deliberately tests failure too: if payment is still broken, checkout remediation does not resolve the incident. The timeline and audit history record both outcomes. This is a local portfolio system; production identity, restart/rollback adapters and longer verification windows remain separate engineering work.”

## Questions and answers

**Why rules and an LLM?** Rules provide reproducible operation and tests. The model is optional explanation, never the source of execution authority.

**How do you prevent hallucinated evidence?** Every citation must match an ID supplied to the model; invalid or malformed output falls back to rules. Correct citations still do not prove causal reasoning, so findings retain alternatives and uncertainty.

**Why does verification read fresh counters?** A one-minute Prometheus window can contain the pre-action failures. Fresh counter deltas and new business requests test what happened after execution.

**How does deduplication work?** A unique nullable open key per service/rule plus serialized polling prevents multiple open records; persistence and a post-resolution cooldown reduce noise.

**How is replay handled?** A conditional SQL update claims execution once. Subsequent calls read the stored state. The demo checks the approved scenario revision too.

**What happens if the process crashes?** It does not assume success. An abandoned action eventually becomes failed/inconclusive and the incident remains unresolved.

**What would you change for production?** Use a real identity provider with short-lived sessions and individual audit identity, immutable audit storage, distributed workers/quotas, infrastructure-specific allowlisted adapters, a trace collector, longer SLO observation windows and stronger failure/load testing.

## Publication checklist

Run the unit, lint, frontend and live verification commands; review the acceptance checklist; include real screenshots; ensure `.env` and credentials are ignored; audit packages and container images; review the Git diff; create a repository only when explicitly requested; push and verify CI; record a demonstration showing both failed and successful recovery. Do not claim cloud deployment or live-model testing that was not performed.

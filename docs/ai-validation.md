# Live AI validation — 2026-10-19

The already-installed local `qwen2.5:7b-instruct` model was exercised through the actual Ollama adapter using retained observations and scenario evidence from a real detected incident. It returned a schema-valid response with valid supplied evidence IDs in 115.45 seconds. See live-ai-verification.json for the exact response and incident references.

Run `.venv\Scripts\python.exe scripts/verify_live_ai.py --model qwen2.5:7b-instruct --timeout 180` to reproduce. This script tests the adapter directly against the local Ollama server; it does not change the dashboard provider or install/download a model. The timeout is bounded to 5–180 seconds per attempt, with two attempts maximum. The default remains 15 seconds and deterministic mock mode.

## Interpretation review: not a factual-accuracy pass

The model's explanation claimed that no errors were recorded even though the error-rate observation was unavailable, and described restart capability/scenario expiry as an upcoming restart. Neither claim is established by the evidence. It also conflated application health with Prometheus health reporting. Valid JSON and valid citations do not prove correct interpretation.

Keep deterministic diagnosis as the default. The model is advisory, has no tool authority, and cannot authorize execution. Broader evaluation and factual consistency checks are still needed before recommending its findings without review.

## Adapter hardening

Citations now validate against the sanitized evidence actually sent to the model, rather than the larger internal evidence set. Tests reject citations to excluded log evidence. Invalid timeout configuration falls back explicitly instead of using unbounded waits. The 52-test suite includes provider success, provider failure, unsupported citations and configuration bounds.

To opt into the dashboard provider later, set AI_PROVIDER=ollama, OLLAMA_MODEL to an installed model and AI_TIMEOUT_SECONDS appropriately, then recreate the backend. OLLAMA_URL defaults to host.docker.internal:11434 inside Compose. No such configuration change was made during this validation.


## Factual-summary guardrails

The adapter now returns `ollama-guarded` when a model response validates. The authoritative summary is generated directly from the retained observation and scenario: missing metrics are explicitly unavailable, and health/readiness are distinct. Expected recovery, abort conditions, risk and recommended action come from deterministic rules. Model text is retained only as interpretation: its cause is prefixed `AI hypothesis (unverified)`, confidence cannot exceed medium, and mandatory limitations explain that scenario expiry is not a restart schedule or recovery guarantee. Alternative hypotheses and suggested next steps remain model-authored and require review.

This constrains the fields that previously contained unsupported assertions; it does not prove every model hypothesis true. Regression tests deliberately inject the original zero-error/restart-countdown claims and verify they cannot replace observed facts or recovery policy. Unknown scenarios cannot gain high confidence from a model. List-item text is bounded to prevent oversized individual explanations.

The original model output is preserved in live-ai-before-guardrails.json for comparison. The current validation result is in live-ai-verification.json. The application still defaults to deterministic mode.

Guarded live retest passed on 2026-10-19 in 60.62 seconds with provider ollama-guarded. The persisted result explicitly reports error-rate unavailability, preserves not-ready state, uses three fresh request checks, retains approval-expiry abort conditions and caps confidence. Hypothesis accuracy remains subject to review.

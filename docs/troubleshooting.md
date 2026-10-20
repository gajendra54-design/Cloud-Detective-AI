# Troubleshooting

- Docker pipe unavailable or denied: start Docker Desktop's Linux engine; grant the tool local Docker access when prompted.
- First build is slow: image and package downloads can be large. Inspect `docker compose ps` and build output. Retry `docker compose up --build -d --wait`; cached layers are reused.
- Dashboard disconnected: check backend health at `/api/v1/ready`, then `docker compose logs --tail 100 backend` and database health. Do not paste secrets from docker inspect/config output into chat.
- No rate/latency data: generate demo requests, allow at least two scrapes, and check both targets at Prometheus `/targets`. Missing values are shown as dashes, not fabricated zeros.
- No incident: a threshold must persist for two polls; traffic-based rules require at least three requests in the window. A resolved rule has a 75-second cooldown.
- Proposal rejected: the controlled scenario may have expired, the incident may be resolved, or the exact revision changed. Investigate current state and create a fresh proposal.
- Recovery failed: inspect the saved samples and dependency readiness. A successful control call alone is not success.
- Operator access denied: copy the correct distinct role token from `.env`; an investigator token cannot approve. Tokens in the tab disappear on reload. After 20 failures, wait one minute.
- Local pytest hangs on Windows: the sandbox may block the sockets used by Python's async loop. Run the documented tests with approved local socket access.
- Ollama fallback: make sure the host server is reachable from the backend container and the configured model exists. The system remains useful in deterministic mode; no model result is fabricated.

Stop: `docker compose down`. Do not delete the database volume unless you deliberately want to erase incident history.

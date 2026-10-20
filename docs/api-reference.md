# API reference

Interactive schemas are at http://localhost:8000/docs. Responses use UTC timestamps. Read lists are bounded; incident listing accepts limit (1–100) and offset. Detail routes return 404 for unknown IDs.

Public local reads: GET `/api/v1/health`, `/ready`, `/services`, `/telemetry`, `/incidents`, `/incidents/{id}`, `/incidents/{id}/timeline`, `/incidents/{id}/evidence`, `/incidents/{id}/investigation`, `/remediations`, `/remediations/{id}/verification`, `/audit-events`, `/demo/scenario`.

Investigator bearer token: POST `/incidents/{id}/investigate`, `/incidents/{id}/propose`, `/demo/scenario` (name and duration_seconds), `/demo/traffic` (five bounded requests).

Approver bearer token: POST `/remediations/{id}/approve` with the exact returned fingerprint; POST `/remediations/{id}/reject`; POST `/remediations/{id}/execute`. Approvals expire after five minutes. Forbidden access returns 403; failed-authorization rate limiting returns 429; invalid/stale state returns 409; schema errors return 422. Replaying execution returns its existing status/result.

The lower-level demo control API requires X-Demo-Token, operates only on disposable services, and exists for lab setup/emergency stop. The application API does not expose this token.


Evidence and timeline reads return the latest bounded page in chronological order (timestamp, then ID). Evidence defaults to 100 records, timeline to 200; `limit` can reduce these bounds. Request `?before=<first-record-id>` to retrieve the preceding page. The cursor is scoped to the incident and returns 404 if invalid. New records do not shift an existing cursor. The drawer provides Load older controls and fetches cited evidence outside the current page by its stable ID.

GET `/api/v1/incidents/{incident_id}/evidence/{evidence_id}` retrieves a single record, including old citations. A missing record or a record belonging to another incident returns 404.


Individual accounts: POST `/api/v1/auth/login` with username/password returns a 30-minute bearer session and public user identity. GET `/api/v1/auth/me` validates the session; POST `/api/v1/auth/logout` revokes it. Login failures return generic 401, malformed inputs return redacted 422, and more than ten login attempts per minute in one process returns 429. Session credentials can be used on protected lifecycle routes; the user's assigned role is enforced. Local account administration uses `python -m app.accounts` inside the backend container. See accounts.md.


Proposal POST bodies optionally select `action`: `auto` (default), `restart_service` or `rollback_demo`. Restart requires advertised support and a current boot ID; rollback requires demo-v2 and recorded demo-v1. Unsupported preconditions return 409. Existing pending proposals for a different action must be rejected before proposing another. See recovery-actions.md for exact scope and effects.

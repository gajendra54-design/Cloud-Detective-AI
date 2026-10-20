# Local demonstration threat model

## Boundaries and protections

Published ports are loopback-only; PostgreSQL and payment remain internal. No host socket, privileged container, arbitrary shell/SQL endpoint or production cloud integration exists. Demo scenarios are enumerated and expire within 120 seconds; CPU work is bounded to 50 ms and memory to 8 MiB per serialized request, with container resource limits.

Separate investigator and approver bearer tokens are checked server-side in constant time. The dashboard retains them only in React memory, never browser storage. Twenty failed authorizations in one minute trigger a process-local cooldown, and failures are audited without recording submitted credentials. This is shared-role authentication, not individual identity. APP_MODE rejects non-local-demo values. Production use requires an established identity provider, short-lived sessions, user attribution and distributed rate limiting.

Read endpoints intentionally allow local viewers. Changing endpoints require a role and JSON; CORS is not enabled. Nginx sets frame and content-type protections. React escapes evidence text. Proposal fingerprints, incident versions, expiry, conditional SQL transitions and demo revision preconditions guard against stale approvals and replay. Verification must pass before an incident is resolved.

Telemetry and AI output are untrusted. Only generated, bounded telemetry summaries are collected from fixed internal targets. Redaction removes sensitive keys, bearer strings and email patterns. The model receives only structured observations/scenario state, not raw logs. It has no tools, commands or infrastructure permissions. Output is schema validated and evidence IDs must exist. The model's recommended action cannot directly create or execute a proposal.

Audit APIs provide no edit/delete operations. Database owners can still modify records; cryptographic tamper evidence and separate audit storage are future work. Secrets are neither committed nor included in image contexts.

## Residual risks

A local user holding both role tokens can approve their own actions. Local malware can read .env. The direct checkout control token can bypass the platform workflow for lab operation and emergency stop; it is never given to frontend JavaScript. These are intentional local-demo boundaries, not production guarantees.

Read APIs and telemetry histories have bounded responses, but per-user quotas and comprehensive load testing are incomplete. A local trusted operator can generate repeated incidents/evidence and grow the database. A crash during execution may leave the outcome unknown; expiry handling records failure rather than guessing success. The short verification window and simulated failures are not a reliability certification.

Python and npm package audits are performed during development. Container-image vulnerability scanning and base-image digest pinning remain outstanding. An audit reporting no known vulnerabilities is not proof of security.


## Named local accounts

Named users now have scrypt-hashed passwords and 30-minute revocable sessions whose bearer tokens are stored only as SHA-256 hashes. Account updates invalidate sessions, and every protected action rechecks the current user role and enabled flag. Login validation never echoes submitted passwords. Hashing is serialized and login attempts are limited in the local process. Shared-token compatibility remains enabled by default and can be disabled via LEGACY_TOKENS_ENABLED. Read APIs remain public on loopback. See accounts.md for production limitations and password-hashing sources.


Controlled restart exposes only authenticated self-exit in disposable demo containers with a bounded Compose restart policy. The backend holds no Docker socket. Boot-ID/revision checks and a pending flag prevent repeated or stale changes. In-memory demo data is lost. Bundled-release rollback allows only the recorded v2-to-v1 transition, with no code downloads or arbitrary image selection. Both require human-approved backend proposals and independent verification. The lower-level control token remains a privileged lab/emergency credential, as with scenario controls.

# Local accounts and sessions

Named users supplement the original shared-role tokens. This is local authentication, not production identity infrastructure. Reads of incidents, telemetry and audit records remain public on loopback.

## Create an operator

From the project directory, run these commands in your own terminal. The password prompt hides input; choose distinct passwords of 15–128 characters.

```sh
docker compose exec backend python -m app.accounts investigator --role investigator
docker compose exec backend python -m app.accounts approver --role approver
```

Open Operator access in the dashboard and sign in. Investigator users can activate demo scenarios, gather evidence and propose recovery. Approver users can approve/reject/execute proposals. Viewer users cannot perform protected actions. Sign out and sign in as the other role when demonstrating separation of responsibilities.

Sessions last 30 minutes, use random bearer credentials, and are retained only in React memory. Reloading the page clears browser access. The database holds only session-token hashes. A new login revokes that user's previous session. Explicit Sign out revokes the current session on the server. Closing the access dialog does not sign out.

## Change or disable accounts

Repeat the account command to change a password or role; this revokes previous sessions. Disable an account with:

```sh
docker compose exec backend python -m app.accounts investigator --disable
```

Account administration requires local container/database access, not a public registration endpoint. Account changes and authentication events are audited. Protected actions identify their user as `user:<stable UUID>`; legacy shared credentials still identify only a role.

## Compatibility and limits

Legacy demo tokens remain enabled so existing verification scripts keep working. After creating named users, set `LEGACY_TOKENS_ENABLED=false` in `.env` and recreate the backend to disable that path. Existing token-based lifecycle scripts will then need named session credentials. This switch does not protect public read endpoints or make the system production-ready.

Passwords use salted scrypt with N=2^17, r=8, p=1. Login hashing is serialized in the single local backend process and all login attempts are limited to ten per minute. These limits are process-local; multiple workers require shared rate limiting. This follows [OWASP's scrypt recommendation](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) using [Python hashlib](https://docs.python.org/3/library/hashlib.html).

No cookies are used for authentication, so ambient cookie authority is absent. Bearer credentials must still be protected against XSS. TLS, MFA, external identity, account recovery, a web administration interface, distributed rate limiting and production session policies are not implemented. Do not expose this HTTP demo publicly.

## Verification

`docker compose exec -T backend python verify_accounts.py` tests real PostgreSQL-backed sessions and all three roles through HTTP. It prints no passwords or session tokens and disables its temporary test accounts afterward, preserving the audit trail. Unit tests additionally cover expiry, credential rotation, disabled accounts, invalid login throttling and redacted validation errors.

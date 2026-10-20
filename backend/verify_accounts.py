"""Live local account smoke test. Leaves disabled test accounts and audit history."""

import json
import secrets
from datetime import datetime, timezone
from uuid import uuid4
import httpx
from sqlalchemy import select
from app.accounts import manage_user
from app.db import AuditEvent, database


def main():
    engine, sessions = database()
    usernames = []
    result = {"verified_at": datetime.now(timezone.utc).isoformat(), "checks": []}
    try:
        with httpx.Client(
            base_url="http://127.0.0.1:8000", timeout=15, trust_env=False
        ) as client:
            for role in ("viewer", "investigator", "approver"):
                username, password = (
                    "verify-" + uuid4().hex[:12],
                    secrets.token_urlsafe(24),
                )
                with sessions() as session, session.begin():
                    user = manage_user(session, username, role, password)
                    user_id = user.id
                usernames.append(username)
                login = client.post(
                    "/api/v1/auth/login",
                    json={"username": username, "password": password},
                )
                assert login.status_code == 200, login.status_code
                headers = {"Authorization": "Bearer " + login.json()["token"]}
                assert (
                    client.get("/api/v1/auth/me", headers=headers).json()["user"]["id"]
                    == user_id
                )
                investigate = client.post(
                    "/api/v1/incidents/nonexistent/investigate", headers=headers
                )
                assert investigate.status_code == (
                    404 if role == "investigator" else 403
                )
                approve = client.post(
                    "/api/v1/remediations/nonexistent/approve",
                    headers=headers,
                    json={"fingerprint": "a" * 64},
                )
                assert approve.status_code == (404 if role == "approver" else 403)
                assert (
                    client.post("/api/v1/auth/logout", headers=headers).status_code
                    == 200
                )
                assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
                with sessions() as session:
                    assert session.scalar(
                        select(AuditEvent).where(
                            AuditEvent.actor == "user:" + user_id,
                            AuditEvent.event == "login_succeeded",
                        )
                    )
                result["checks"].append(
                    {
                        "role": role,
                        "login": "PASS",
                        "permissions": "PASS",
                        "logout_revocation": "PASS",
                        "individual_audit": "PASS",
                    }
                )
    finally:
        with sessions() as session, session.begin():
            for username in usernames:
                manage_user(session, username, disable=True)
        engine.dispose()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

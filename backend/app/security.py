import hmac
import time
from uuid import uuid4
from fastapi import Header, HTTPException, Request
from app.config import settings
from app.db import AuditEvent, User, UserSession
from app.accounts import token_hash
from app.services.recovery import utc
from datetime import datetime, timezone


def role(required):
    def check(request: Request, authorization: str = Header(default="")):
        now = time.monotonic()
        with request.app.state.auth_lock:
            attempts = request.app.state.failed_auth
            while attempts and attempts[0] < now - 60:
                attempts.popleft()
            if len(attempts) >= 20:
                raise HTTPException(
                    429, "Too many failed authorization attempts; retry in one minute"
                )
        candidate = authorization.removeprefix("Bearer ").encode()
        config = settings()
        if authorization.startswith("Bearer cd_session_"):
            with request.app.state.sessions() as session:
                login = session.get(UserSession, token_hash(authorization[7:]))
                user = session.get(User, login.user_id) if login else None
                if (
                    login
                    and utc(login.expires_at) > datetime.now(timezone.utc)
                    and user
                    and user.enabled
                    and user.role == required
                ):
                    return "user:" + user.id
        expected = (
            config.approver_token
            if required == "approver"
            else config.investigator_token
        )
        if (
            not config.legacy_tokens_enabled
            or not authorization.startswith("Bearer ")
            or not expected
            or not hmac.compare_digest(candidate, expected.encode())
        ):
            with request.app.state.auth_lock:
                attempts.append(now)
            with request.app.state.sessions() as session, session.begin():
                session.add(
                    AuditEvent(
                        id=str(uuid4()),
                        actor="unauthenticated",
                        event="authorization_denied",
                        subject=required,
                        details={"method": request.method},
                    )
                )
            raise HTTPException(403, f"Valid {required} access is required")
        return required

    return check

from datetime import datetime, timedelta, timezone
import secrets
import time
from uuid import uuid4
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select, delete
from app.accounts import password_matches, token_hash
from app.db import User, UserSession, AuditEvent
from app.services.recovery import utc

router = APIRouter(prefix="/api/v1/auth")


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


def identity(session, authorization):
    if not authorization.startswith("Bearer cd_session_"):
        raise HTTPException(401, "Session expired or invalid")
    record = session.get(UserSession, token_hash(authorization[7:]))
    user = session.get(User, record.user_id) if record else None
    if (
        not record
        or utc(record.expires_at) <= datetime.now(timezone.utc)
        or not user
        or not user.enabled
    ):
        raise HTTPException(401, "Session expired or invalid")
    return user, record


def public_user(user):
    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/login")
def login(body: Login, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    # Serialize memory-hard hashing within this local process and bound all attempts.
    with request.app.state.login_lock:
        now = time.monotonic()
        attempts = request.app.state.login_attempts
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, "Too many login attempts; retry in one minute")
        attempts.append(now)
        with request.app.state.sessions() as session, session.begin():
            user = session.scalar(select(User).where(User.username == body.username))
            encoded = (
                user.password_hash if user else request.app.state.dummy_password_hash
            )
            valid = password_matches(body.password.get_secret_value(), encoded)
            if not valid or not user or not user.enabled:
                session.add(
                    AuditEvent(
                        id=str(uuid4()),
                        actor="unauthenticated",
                        event="login_denied",
                        subject="login",
                        details={},
                    )
                )
                denied = True
            else:
                denied = False
                # One active session per person; a new login revokes previous access.
                session.execute(
                    delete(UserSession).where(
                        (UserSession.user_id == user.id)
                        | (UserSession.expires_at <= datetime.now(timezone.utc))
                    )
                )
                token = "cd_session_" + secrets.token_urlsafe(32)
                expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
                session.add(
                    UserSession(
                        token_hash=token_hash(token), user_id=user.id, expires_at=expiry
                    )
                )
                session.add(
                    AuditEvent(
                        id=str(uuid4()),
                        actor="user:" + user.id,
                        event="login_succeeded",
                        subject=user.id,
                        details={},
                    )
                )
                result = {
                    "token": token,
                    "expires_at": expiry,
                    "user": public_user(user),
                }
        if denied:
            raise HTTPException(401, "Invalid username or password")
        return result


@router.get("/me")
def me(request: Request, response: Response, authorization: str = Header(default="")):
    response.headers["Cache-Control"] = "no-store"
    with request.app.state.sessions() as session:
        user, record = identity(session, authorization)
        return {"user": public_user(user), "expires_at": record.expires_at}


@router.post("/logout")
def logout(request: Request, authorization: str = Header(default="")):
    with request.app.state.sessions() as session, session.begin():
        user, record = identity(session, authorization)
        session.delete(record)
        session.add(
            AuditEvent(
                id=str(uuid4()),
                actor="user:" + user.id,
                event="logout",
                subject=user.id,
                details={},
            )
        )
    return {"status": "signed_out"}

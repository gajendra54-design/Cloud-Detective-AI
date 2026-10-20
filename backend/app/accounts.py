"""Password hashing and local operator account management. Never log secrets."""

import argparse
import getpass
import hashlib
import hmac
import re
import secrets
from uuid import uuid4
from sqlalchemy import select, delete
from app.db import User, UserSession, AuditEvent, database


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=2**17,
        r=8,
        p=1,
        maxmem=192 * 1024 * 1024,
        dklen=32,
    )
    return f"scrypt${salt}${digest.hex()}"


def password_matches(password, encoded):
    try:
        kind, salt, _ = encoded.split("$")
        return kind == "scrypt" and hmac.compare_digest(
            password_hash(password, salt), encoded
        )
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def manage_user(session, username, role=None, password=None, disable=False):
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{2,63}", username):
        raise ValueError(
            "Username must be 3–64 lowercase letters, digits, dots, underscores or hyphens"
        )
    user = session.scalar(select(User).where(User.username == username))
    if disable:
        if user is None:
            raise ValueError("User not found")
        user.enabled = False
    else:
        if (
            role not in {"viewer", "investigator", "approver"}
            or password is None
            or not 15 <= len(password) <= 128
        ):
            raise ValueError("Choose a valid role and a 15–128 character password")
        if user is None:
            user = User(id=str(uuid4()), username=username)
            session.add(user)
        user.role, user.password_hash, user.enabled = (
            role,
            password_hash(password),
            True,
        )
    session.flush()
    session.execute(delete(UserSession).where(UserSession.user_id == user.id))
    session.add(
        AuditEvent(
            id=str(uuid4()),
            actor="local-admin-cli",
            event="user_disabled" if disable else "user_configured",
            subject=user.id,
            details={"username": username, "role": user.role},
        )
    )
    return user


def main():
    parser = argparse.ArgumentParser(
        description="Manage local users; changes revoke all existing sessions"
    )
    parser.add_argument("username")
    parser.add_argument("--role", choices=["viewer", "investigator", "approver"])
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    password = None
    if not args.disable:
        if not args.role:
            parser.error("--role is required unless disabling a user")
        password = getpass.getpass("Password (15–128 characters): ")
        if password != getpass.getpass("Confirm password: "):
            parser.error("Passwords do not match")
    engine, sessions = database()
    try:
        with sessions() as session, session.begin():
            manage_user(session, args.username, args.role, password, args.disable)
        print("User updated; previous sessions revoked.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

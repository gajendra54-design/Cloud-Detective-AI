import asyncio
from collections import deque
from threading import Lock
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import request_validation_exception_handler
from sqlalchemy import text
from app.db import database_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.api.routes import router
from app.api.lifecycle import router as lifecycle_router
from app.workers.monitor import monitor
from app.api.auth import router as auth_router
from app.accounts import password_hash
import secrets


@asynccontextmanager
async def lifespan(app):
    config = settings()
    engine = database_engine(config.database_url)
    app.state.sessions = sessionmaker(engine, expire_on_commit=False)
    app.state.readiness_probe = None
    app.state.failed_auth = deque(maxlen=20)
    app.state.auth_lock = Lock()
    app.state.login_lock = Lock()
    app.state.login_attempts = deque(maxlen=10)
    app.state.dummy_password_hash = password_hash(secrets.token_urlsafe(32))
    app.state.monitor_status = {"last_poll": None, "error": None}
    task = (
        asyncio.create_task(
            monitor(config, app.state.sessions, app.state.monitor_status)
        )
        if config.worker_enabled
        else None
    )
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        engine.dispose()


app = FastAPI(title="Cloud Detective AI", version="0.3.0", lifespan=lifespan)
app.include_router(router)
app.include_router(auth_router)
app.include_router(lifecycle_router)


@app.get("/api/v1/health")
def health():
    return {"status": "alive", "stage": "core-lifecycle"}


def probe_database():
    with app.state.sessions() as session:
        session.execute(text("SELECT 1"))


@app.get("/api/v1/ready")
async def ready():
    try:
        probe = app.state.readiness_probe
        if probe is None or probe.done():
            if probe is not None and not probe.cancelled():
                probe.exception()  # Consume a late failure from the previous probe.
            probe = asyncio.create_task(asyncio.to_thread(probe_database))
            app.state.readiness_probe = probe
        # Share one outstanding probe so a slow resolver cannot multiply threads.
        await asyncio.wait_for(asyncio.shield(probe), timeout=2)
        return {"status": "ready"}
    except Exception:
        raise HTTPException(503, "Database unavailable") from None


@app.exception_handler(RequestValidationError)
async def safe_validation(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api/v1/auth/"):
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid authentication request"},
            headers={"Cache-Control": "no-store"},
        )
    return await request_validation_exception_handler(request, exc)

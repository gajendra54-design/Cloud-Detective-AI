import asyncio
import logging
from datetime import datetime, timedelta, timezone
import httpx
from sqlalchemy import delete, text, select
from app.db import TelemetrySample, Remediation, AuditEvent
from uuid import uuid4
from app.services.telemetry import observe
from app.services.detection import record

logger = logging.getLogger("monitor")


def persist_observations(config, sessions, observations):
    with sessions() as session, session.begin():
        # A transaction-scoped leader lock prevents duplicate polling writes across workers.
        if session.bind.dialect.name == "postgresql" and not session.scalar(
            text("SELECT pg_try_advisory_xact_lock(41702026)")
        ):
            return
        now = datetime.now(timezone.utc)
        for action in session.scalars(
            select(Remediation).where(
                Remediation.expires_at < now,
                Remediation.status.in_(
                    [
                        "PENDING_APPROVAL",
                        "APPROVED",
                        "EXECUTING",
                        "VERIFYING",
                    ]
                ),
            )
        ):
            previous = action.status
            action.status = (
                "EXPIRED" if previous in {"PENDING_APPROVAL", "APPROVED"} else "FAILED"
            )
            if action.status == "FAILED":
                action.result = {
                    "passed": False,
                    "reason": "Execution did not complete before expiry; outcome unknown. Incident remains unresolved.",
                }
            session.add(
                AuditEvent(
                    id=str(uuid4()),
                    actor="system",
                    event="proposal_expired"
                    if action.status == "EXPIRED"
                    else "execution_abandoned",
                    subject=action.id,
                    details={"previous_status": previous},
                )
            )
        for observation in observations:
            record(session, observation, config)
        session.execute(
            delete(TelemetrySample).where(
                TelemetrySample.created_at
                < datetime.now(timezone.utc) - timedelta(hours=1)
            )
        )


async def monitor(config, sessions, status):
    async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
        while True:
            try:
                observations = await asyncio.gather(
                    *(observe(config, name, client) for name in config.targets)
                )
                await asyncio.to_thread(
                    persist_observations, config, sessions, observations
                )
                status.update(
                    last_poll=datetime.now(timezone.utc).isoformat(), error=None
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                # Never include connection URLs, auth tokens or upstream payloads.
                logger.error("monitor cycle failed")
                status.update(error="Monitoring cycle failed; telemetry may be stale")
            await asyncio.sleep(config.poll_seconds)

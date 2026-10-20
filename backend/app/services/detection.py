from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy import select
from app.db import DetectionState, Incident, TimelineEvent, Evidence, TelemetrySample


def rules(observation, config):
    fired = []
    if observation.health == "unavailable":
        fired.append("service_unavailable")
    elif observation.ready is False:
        fired.append("service_not_ready")
    if (observation.request_count_window or 0) >= 3:
        if (
            observation.error_rate is not None
            and observation.error_rate > config.error_threshold
        ):
            fired.append("high_error_rate")
        if (
            observation.latency_p95 is not None
            and observation.latency_p95 > config.latency_threshold
        ):
            fired.append("high_latency")
    return fired


def record(session, observation, config, now=None):
    now = now or datetime.now(timezone.utc)
    session.add(
        TelemetrySample(
            id=str(uuid4()),
            service_id=observation.service,
            data=observation.model_dump(),
            created_at=now,
        )
    )
    fired = rules(observation, config)
    for rule in [
        "service_unavailable",
        "service_not_ready",
        "high_error_rate",
        "high_latency",
    ]:
        key = f"{observation.service}:{rule}"
        state = session.get(DetectionState, key)
        if state is None:
            state = DetectionState(id=key, consecutive=0)
            session.add(state)
        state.consecutive = state.consecutive + 1 if rule in fired else 0
        if state.consecutive < config.persistence_polls:
            continue
        existing = session.scalar(select(Incident).where(Incident.open_key == key))
        if existing:
            continue
        recent = session.scalar(
            select(TimelineEvent)
            .join(Incident, Incident.id == TimelineEvent.incident_id)
            .where(
                Incident.service_id == observation.service,
                Incident.rule == rule,
                Incident.status == "RESOLVED",
                TimelineEvent.created_at > now - timedelta(seconds=75),
            )
            .limit(1)
        )
        if recent:
            continue
        incident = Incident(
            id=str(uuid4()),
            service_id=observation.service,
            status="OPEN",
            rule=rule,
            open_key=key,
            severity="critical" if rule == "service_unavailable" else "warning",
            version=1,
            created_at=now,
        )
        session.add(incident)
        session.flush()
        evidence = Evidence(
            id=str(uuid4()),
            incident_id=incident.id,
            source="Prometheus + demo health endpoints",
            kind="observation",
            data=observation.model_dump(),
            created_at=now,
        )
        session.add(evidence)
        session.add(
            TimelineEvent(
                id=str(uuid4()),
                incident_id=incident.id,
                details={"type": "detected", "rule": rule, "evidence_id": evidence.id},
                created_at=now,
            )
        )
    return fired

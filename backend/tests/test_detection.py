from datetime import datetime, timezone
import httpx
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from app.config import Settings
from app.db import Base, Service, Incident, Evidence
from app.services.detection import record, rules
from app.services.telemetry import Observation, observe


def observation(**overrides):
    values = dict(
        service="checkout",
        observed_at=datetime.now(timezone.utc).isoformat(),
        health="healthy",
        ready=True,
        telemetry_status="available",
        error_rate=0.8,
        request_count_window=20,
        latency_p95=0.05,
    )
    return Observation(**(values | overrides))


def test_persistence_deduplication_and_evidence():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    config = Settings(database_url="sqlite://")
    with Session(engine) as session:
        session.add(Service(id="checkout", name="Checkout"))
        session.commit()
        record(session, observation(), config)
        session.commit()
        assert session.scalar(select(func.count()).select_from(Incident)) == 0
        for _ in range(4):
            record(session, observation(), config)
            session.commit()
        assert session.scalar(select(func.count()).select_from(Incident)) == 1
        assert session.scalar(select(Evidence)).data["error_rate"] == 0.8


def test_missing_and_low_traffic_do_not_trigger_rate_incident():
    config = Settings(database_url="sqlite://")
    assert rules(observation(error_rate=None, latency_p95=None), config) == []
    assert rules(observation(request_count_window=1), config) == []
    assert rules(observation(error_rate=0, latency_p95=0.4), config) == ["high_latency"]


def test_persistence_resets_on_healthy_observation():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    config = Settings(database_url="sqlite://")
    with Session(engine) as session:
        session.add(Service(id="checkout", name="Checkout"))
        session.commit()
        for obs in [observation(), observation(error_rate=0), observation()]:
            record(session, obs, config)
            session.commit()
        assert session.scalar(select(func.count()).select_from(Incident)) == 0


def test_prometheus_unavailable_is_explicit():
    import asyncio

    def handler(request):
        if request.url.path in {"/health", "/ready"}:
            return httpx.Response(200, json={"status": "ready"})
        return httpx.Response(503)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await observe(Settings(database_url="sqlite://"), "checkout", client)

    result = asyncio.run(run())
    assert result.telemetry_status == "unavailable"
    assert result.error_rate is None
    assert len(result.missing) == 4

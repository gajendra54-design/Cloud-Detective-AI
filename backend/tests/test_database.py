from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.db import Base, Service, Incident, TimelineEvent


def test_persistence(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Service(id="checkout", name="Checkout"))
        session.flush()
        session.add(Incident(id="incident", service_id="checkout", rule="errors"))
        session.flush()
        session.add(
            TimelineEvent(
                id="event", incident_id="incident", details={"type": "detected"}
            )
        )
        session.commit()
    with Session(engine) as session:
        assert session.scalar(select(TimelineEvent)).details == {"type": "detected"}


def test_actual_migration(tmp_path, monkeypatch):
    from pathlib import Path
    from alembic.config import Config
    from alembic import command

    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = create_engine(url)
    with Session(engine) as session:
        assert set(session.scalars(select(Service.id))) == {"checkout", "payment"}
    engine.dispose()

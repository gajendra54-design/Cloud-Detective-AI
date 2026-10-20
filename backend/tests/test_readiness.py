import asyncio
import threading

from fastapi import HTTPException

from app import main


def test_slow_database_probe_is_bounded_and_shared(monkeypatch):
    release = threading.Event()
    calls = []

    def blocked_probe():
        calls.append(1)
        release.wait(8)

    monkeypatch.setattr(main, "probe_database", blocked_probe)
    monkeypatch.setattr(main.app.state, "readiness_probe", None, raising=False)

    async def run():
        try:
            results = await asyncio.gather(
                main.ready(), main.ready(), return_exceptions=True
            )
            assert all(
                isinstance(r, HTTPException) and r.status_code == 503 for r in results
            )
            assert len(calls) == 1
            assert main.health()["status"] == "alive"
        finally:
            release.set()
            await main.app.state.readiness_probe
        assert await main.ready() == {"status": "ready"}

    asyncio.run(run())

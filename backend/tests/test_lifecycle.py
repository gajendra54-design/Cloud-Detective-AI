import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.config import settings
from app.db import Base, Service, Incident, Remediation
from app.main import app
from app.services.investigation import diagnose, sanitize, validate_finding, investigate
from app.services.recovery import verify


@pytest.fixture
def platform(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'platform.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("WORKER_ENABLED", "false")
    monkeypatch.setenv("INVESTIGATOR_TOKEN", "investigator-test")
    monkeypatch.setenv("APPROVER_TOKEN", "approver-test")
    monkeypatch.setenv("DEMO_CONTROL_TOKEN", "demo-test")
    settings.cache_clear()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Service(id="checkout", name="Checkout"))
        session.flush()
        session.add(
            Incident(
                id="incident",
                service_id="checkout",
                rule="high_error_rate",
                status="OPEN",
                version=1,
                open_key="checkout:high_error_rate",
            )
        )
        session.commit()
    state = {
        "name": "errors",
        "revision": "revision1",
        "requests": 0,
        "errors": 0,
        "force_fail": False,
        "changes": 0,
        "boot_id": "boot1",
        "restart_enabled": True,
    }

    def upstream(request):
        path = request.url.path
        if path == "/api/v1/query":
            return httpx.Response(
                200, json={"status": "success", "data": {"result": []}}
            )
        if path == "/health":
            return httpx.Response(
                200, json={"status": "alive", "boot_id": state["boot_id"]}
            )
        if path == "/ready":
            return httpx.Response(503 if state["force_fail"] else 200)
        if path == "/control/evidence":
            return httpx.Response(200, json={"logs": [], "traces": [], "changes": []})
        if path == "/control/scenario":
            if request.method == "POST":
                import json

                body = json.loads(request.content)
                if (
                    body.get("expected_revision")
                    and body["expected_revision"] != state["revision"]
                ):
                    return httpx.Response(409)
                state.update(
                    name=body["name"],
                    revision=str(uuid4()),
                    changes=state["changes"] + 1,
                )
            return httpx.Response(
                200,
                json={
                    "name": state["name"],
                    "revision": state["revision"],
                    "boot_id": state["boot_id"],
                    "restart_enabled": state["restart_enabled"],
                    "deployment_version": "demo-v2"
                    if state["name"] == "deployment"
                    else "demo-v1",
                    "previous_version": "demo-v1"
                    if state["name"] == "deployment"
                    else None,
                },
            )
        if path == "/control/rollback":
            import json

            body = json.loads(request.content)
            if (
                state["name"] != "deployment"
                or body["expected_revision"] != state["revision"]
            ):
                return httpx.Response(409)
            state.update(
                name="healthy", revision="rolled-back", changes=state["changes"] + 1
            )
            return httpx.Response(200, json={"version": "demo-v1"})
        if path == "/control/restart":
            import json

            body = json.loads(request.content)
            if (
                body["expected_revision"] != state["revision"]
                or body["expected_boot_id"] != state["boot_id"]
            ):
                return httpx.Response(409)
            state.update(
                name="healthy",
                boot_id="boot2",
                revision="revision2",
                changes=state["changes"] + 1,
            )
            return httpx.Response(202)
        if path == "/api/checkout":
            state["requests"] += 1
            if state["force_fail"]:
                state["errors"] += 1
            return httpx.Response(
                503 if state["force_fail"] else 201, json={"id": "order"}
            )
        if path == "/metrics":
            return httpx.Response(
                200,
                text=f'demo_requests_total{{route="/api/checkout",status="201"}} {state["requests"]-state["errors"]}\ndemo_requests_total{{route="/api/checkout",status="503"}} {state["errors"]}\n',
            )
        raise AssertionError(str(request.url))

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(upstream), **kwargs),
    )

    async def quick_verify(config, target, client):
        return await verify(config, target, client, interval=0)

    monkeypatch.setattr("app.api.lifecycle.verify", quick_verify)
    with TestClient(app) as client:
        yield client, state, engine
    settings.cache_clear()
    engine.dispose()


INV = {"Authorization": "Bearer investigator-test"}
APP = {"Authorization": "Bearer approver-test"}


def proposal(client):
    r = client.post("/api/v1/incidents/incident/investigate", headers=INV)
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/incidents/incident/propose", headers=INV)
    assert r.status_code == 200, r.text
    return r.json()


def approve(client, action):
    return client.post(
        f'/api/v1/remediations/{action["id"]}/approve',
        headers=APP,
        json={"fingerprint": action["fingerprint"]},
    )


def test_full_lifecycle_and_replay(platform):
    client, state, _ = platform
    action = proposal(client)
    assert approve(client, action).status_code == 200
    route = f'/api/v1/remediations/{action["id"]}/execute'
    result = client.post(route, headers=APP)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "SUCCEEDED"
    assert result.json()["result"]["new_requests"] == 3
    assert client.get("/api/v1/incidents/incident").json()["status"] == "RESOLVED"
    again = client.post(route, headers=APP)
    assert again.json()["status"] == "SUCCEEDED"
    assert state["changes"] == 1 and state["requests"] == 3
    assert len(client.get("/api/v1/audit-events").json()) == 5


def test_failed_verification_keeps_incident_open(platform):
    client, state, _ = platform
    action = proposal(client)
    approve(client, action)
    state["force_fail"] = True
    result = client.post(
        f'/api/v1/remediations/{action["id"]}/execute', headers=APP
    ).json()
    assert result["status"] == "FAILED"
    assert result["result"]["new_errors"] == 3
    assert client.get("/api/v1/incidents/incident").json()["status"] == "OPEN"


def test_wrong_role_and_unapproved_execution(platform):
    client, _, _ = platform
    assert client.post("/api/v1/incidents/incident/investigate").status_code == 403
    action = proposal(client)
    root = f'/api/v1/remediations/{action["id"]}'
    assert (
        client.post(
            root + "/approve", headers=INV, json={"fingerprint": action["fingerprint"]}
        ).status_code
        == 403
    )
    assert client.post(root + "/execute", headers=APP).status_code == 409
    assert (
        client.post(
            root + "/approve", headers=APP, json={"fingerprint": "a" * 64}
        ).status_code
        == 409
    )


def test_stale_scenario_does_not_execute(platform):
    client, state, _ = platform
    action = proposal(client)
    approve(client, action)
    state["revision"] = "another-revision"
    response = client.post(f'/api/v1/remediations/{action["id"]}/execute', headers=APP)
    assert response.json()["status"] == "FAILED"
    assert state["changes"] == 0
    assert client.get("/api/v1/incidents/incident").json()["status"] == "OPEN"


def test_expired_and_tampered_approval(platform):
    client, _, engine = platform
    action = proposal(client)
    approve(client, action)
    with Session(engine) as session:
        row = session.get(Remediation, action["id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()
    assert (
        client.post(
            f'/api/v1/remediations/{action["id"]}/execute', headers=APP
        ).status_code
        == 409
    )


def test_rejection_and_proposal_reuse(platform):
    client, _, _ = platform
    action = proposal(client)
    again = client.post("/api/v1/incidents/incident/propose", headers=INV).json()
    assert again["id"] == action["id"]
    assert (
        client.post(
            f'/api/v1/remediations/{action["id"]}/reject', headers=APP
        ).status_code
        == 200
    )
    assert approve(client, action).status_code == 409


def test_diagnosis_citations_and_sanitization():
    evidence = [
        {
            "id": "e1",
            "kind": "observation",
            "data": {"service": "checkout", "error_rate": 1},
        },
        {"id": "e2", "kind": "scenario", "data": {"name": "database"}},
    ]
    finding = diagnose(evidence)
    assert "database" in finding.probable_cause
    assert validate_finding(finding.model_dump(), evidence)
    bad = finding.model_dump() | {"supporting_evidence_ids": ["fabricated"]}
    with pytest.raises(ValueError):
        validate_finding(bad, evidence)
    with pytest.raises(ValueError):
        validate_finding(finding.model_dump() | {"command": "rm -rf /"}, evidence)
    assert sanitize({"token": "secret", "text": "Bearer abc user@example.com"}) == {
        "text": "[REDACTED] [REDACTED_EMAIL]"
    }


def test_provider_failure_falls_back(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    original = httpx.AsyncClient

    def fail(request):
        raise httpx.ConnectError("Unavailable")

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(fail), **kwargs),
    )
    finding, provider = asyncio.run(
        investigate([{"id": "e1", "kind": "observation", "data": {"ready": False}}])
    )
    assert provider == "rules-fallback-provider-error"
    assert finding.confidence == "low"


def test_failed_authorization_is_audited_and_rate_limited(platform):
    client, _, _ = platform
    for _ in range(20):
        assert client.post("/api/v1/incidents/incident/investigate").status_code == 403
    assert client.post("/api/v1/incidents/incident/investigate").status_code == 429
    events = client.get("/api/v1/audit-events").json()
    assert len(events) == 20 and all(
        e["event"] == "authorization_denied" for e in events
    )


def test_health_check_can_resolve_without_changing_scenario(platform):
    client, state, _ = platform
    state["name"] = "healthy"
    action = proposal(client)
    assert action["action"] == "health_check"
    assert approve(client, action).status_code == 200
    response = client.post(f'/api/v1/remediations/{action["id"]}/execute', headers=APP)
    assert response.json()["status"] == "SUCCEEDED"
    assert state["changes"] == 0 and state["requests"] == 3


@pytest.mark.parametrize(
    "resource,model_name,cap",
    [("evidence", "Evidence", 100), ("timeline", "TimelineEvent", 200)],
)
def test_history_pagination_keeps_recent_records_and_tied_timestamps(
    platform, resource, model_name, cap
):
    from app import db

    client, _, engine = platform
    model = getattr(db, model_name)
    stamp = datetime.now(timezone.utc)
    with Session(engine) as session:
        for n in range(cap + 5):
            fields = (
                {"source": "test", "kind": "observation", "data": {}}
                if resource == "evidence"
                else {"details": {"type": "test"}}
            )
            session.add(
                model(
                    id=f"record-{n:04}",
                    incident_id="incident",
                    created_at=stamp,
                    **fields,
                )
            )
        session.commit()
    route = f"/api/v1/incidents/incident/{resource}"
    recent = client.get(route).json()
    assert len(recent) == cap
    assert recent[-1]["id"] == f"record-{cap + 4:04}"
    older = client.get(route, params={"before": recent[0]["id"]}).json()
    assert [row["id"] for row in older] == [f"record-{n:04}" for n in range(5)]
    assert client.get(route, params={"before": older[0]["id"]}).json() == []
    assert client.get(route, params={"limit": cap + 1}).status_code == 422
    assert client.get(route, params={"before": "missing"}).status_code == 404
    if resource == "evidence":
        assert client.get(route + "/record-0000").json()["id"] == "record-0000"
        assert (
            client.get("/api/v1/incidents/other/evidence/record-0000").status_code
            == 404
        )


@pytest.mark.parametrize("user_role", ["viewer", "investigator", "approver"])
def test_named_accounts_enforce_roles_and_logout(platform, user_role):
    from app.accounts import manage_user, token_hash
    from app.db import UserSession

    client, _, engine = platform
    with Session(engine) as session, session.begin():
        user = manage_user(session, "operator", user_role, "long-test-password-123")
        user_id = user.id
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "long-test-password-123"},
    )
    assert login.status_code == 200, login.text
    assert login.headers["cache-control"] == "no-store"
    token = login.json()["token"]
    headers = {"Authorization": "Bearer " + token}
    with Session(engine) as session:
        assert session.get(UserSession, token_hash(token)).user_id == user_id
        assert session.get(UserSession, token) is None
    assert (
        client.get("/api/v1/auth/me", headers=headers).json()["user"]["role"]
        == user_role
    )
    action = proposal(client)
    response = client.post(
        f'/api/v1/remediations/{action["id"]}/approve',
        headers=headers,
        json={"fingerprint": action["fingerprint"]},
    )
    assert response.status_code == (200 if user_role == "approver" else 403)
    if user_role == "approver":
        with Session(engine) as session:
            assert (
                session.get(Remediation, action["id"]).approved_by == "user:" + user_id
            )
    assert client.post(
        "/api/v1/incidents/incident/investigate", headers=headers
    ).status_code == (200 if user_role == "investigator" else 403)
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_session_expiry_disable_rotation_and_secret_redaction(platform, monkeypatch):
    from app.accounts import manage_user, token_hash
    from app.db import UserSession

    client, _, engine = platform
    with Session(engine) as session, session.begin():
        manage_user(session, "operator", "investigator", "long-test-password-123")
    body = {"username": "operator", "password": "long-test-password-123"}
    first = client.post("/api/v1/auth/login", json=body).json()["token"]
    second = client.post("/api/v1/auth/login", json=body).json()["token"]
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer " + first}
        ).status_code
        == 401
    )
    headers = {"Authorization": "Bearer " + second}
    with Session(engine) as session, session.begin():
        session.get(UserSession, token_hash(second)).expires_at = datetime.now(
            timezone.utc
        ) - timedelta(seconds=1)
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert (
        client.post(
            "/api/v1/incidents/incident/investigate", headers=headers
        ).status_code
        == 403
    )
    third = client.post("/api/v1/auth/login", json=body).json()["token"]
    with Session(engine) as session, session.begin():
        manage_user(session, "operator", disable=True)
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer " + third}
        ).status_code
        == 401
    )
    assert client.post("/api/v1/auth/login", json=body).status_code == 401
    body["password"] = "sensitive" * 100
    response = client.post("/api/v1/auth/login", json=body)
    assert response.status_code == 422 and "sensitive" not in response.text
    monkeypatch.setenv("LEGACY_TOKENS_ENABLED", "false")
    settings.cache_clear()
    assert (
        client.post("/api/v1/incidents/incident/investigate", headers=INV).status_code
        == 403
    )


def test_login_throttle_and_generic_failures(platform):
    client, _, _ = platform
    for _ in range(10):
        response = client.post(
            "/api/v1/auth/login", json={"username": "unknown", "password": "wrong"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid username or password"
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "unknown", "password": "wrong"}
        ).status_code
        == 429
    )


@pytest.mark.parametrize("failure", [False, True])
def test_restart_lifecycle_requires_verification_and_replays_once(platform, failure):
    client, state, _ = platform
    client.post("/api/v1/incidents/incident/investigate", headers=INV)
    response = client.post(
        "/api/v1/incidents/incident/propose",
        headers=INV,
        json={"action": "restart_service"},
    )
    assert response.status_code == 200
    action = response.json()
    assert action["parameters"]["expected_boot_id"] == "boot1"
    assert approve(client, action).status_code == 200
    state["force_fail"] = failure
    route = f'/api/v1/remediations/{action["id"]}/execute'
    result = client.post(route, headers=APP).json()
    assert result["status"] == ("FAILED" if failure else "SUCCEEDED")
    assert result["result"]["restart"]["new_boot_id"] == "boot2"
    assert client.get("/api/v1/incidents/incident").json()["status"] == (
        "OPEN" if failure else "RESOLVED"
    )
    assert client.post(route, headers=APP).json()["status"] == result["status"]
    assert state["changes"] == 1


def test_restart_rejects_unsupported_target_and_changed_boot(platform):
    client, state, _ = platform
    client.post("/api/v1/incidents/incident/investigate", headers=INV)
    state["restart_enabled"] = False
    route = "/api/v1/incidents/incident/propose"
    assert (
        client.post(route, headers=INV, json={"action": "restart_service"}).status_code
        == 409
    )
    state["restart_enabled"] = True
    action = client.post(route, headers=INV, json={"action": "restart_service"}).json()
    approve(client, action)
    state["boot_id"] = "unexpected-restart"
    result = client.post(
        f'/api/v1/remediations/{action["id"]}/execute', headers=APP
    ).json()
    assert result["status"] == "FAILED" and state["changes"] == 0


@pytest.mark.parametrize("failure", [False, True])
def test_demo_rollback_lifecycle(platform, failure):
    client, state, _ = platform
    client.post("/api/v1/incidents/incident/investigate", headers=INV)
    route = "/api/v1/incidents/incident/propose"
    assert (
        client.post(route, headers=INV, json={"action": "rollback_demo"}).status_code
        == 409
    )
    state["name"] = "deployment"
    action = client.post(route, headers=INV, json={"action": "rollback_demo"}).json()
    assert action["parameters"]["target_version"] == "demo-v1"
    assert approve(client, action).status_code == 200
    state["force_fail"] = failure
    route = f'/api/v1/remediations/{action["id"]}/execute'
    result = client.post(route, headers=APP).json()
    assert result["status"] == ("FAILED" if failure else "SUCCEEDED")
    assert result["result"]["rollback"]["version"] == "demo-v1"
    client.post(route, headers=APP)
    assert state["changes"] == 1


@pytest.mark.parametrize("cite_hidden", [False, True])
def test_provider_may_only_cite_evidence_actually_sent(monkeypatch, cite_hidden):
    import json

    monkeypatch.setenv("AI_PROVIDER", "ollama")
    evidence = [
        {"id": "visible", "kind": "observation", "data": {"ready": False}},
        {"id": "not-sent", "kind": "demo_records", "data": {"logs": ["untrusted"]}},
    ]
    finding = diagnose(evidence).model_dump()
    finding["supporting_evidence_ids"] = ["not-sent" if cite_hidden else "visible"]
    original = httpx.AsyncClient

    def respond(request):
        body = json.loads(request.content)
        assert "not-sent" not in body["messages"][-1]["content"]
        return httpx.Response(200, json={"message": {"content": json.dumps(finding)}})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
    )
    _, provider = asyncio.run(investigate(evidence))
    assert provider == (
        "rules-fallback-provider-error" if cite_hidden else "ollama-guarded"
    )


def test_ai_timeout_configuration_is_bounded(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    for timeout in ("0", "181", "nan", "invalid"):
        monkeypatch.setenv("AI_TIMEOUT_SECONDS", timeout)
        _, provider = asyncio.run(investigate([]))
        assert provider == "rules-fallback-invalid-timeout"


def test_model_cannot_override_observations_or_recovery_policy():
    from app.services.investigation import ground_model_finding

    evidence = [
        {
            "id": "obs",
            "kind": "observation",
            "data": {"service": "checkout", "ready": False, "error_rate": None},
        },
        {
            "id": "scenario",
            "kind": "scenario",
            "data": {
                "name": "deployment",
                "restart_enabled": True,
                "remaining_seconds": 120,
            },
        },
    ]
    hallucination = diagnose(evidence).model_copy(
        update={
            "summary": "Zero errors; restarting in 120 seconds",
            "confidence": "high",
            "expected_recovery": "Recovery guaranteed in 120 seconds",
            "abort_conditions": "Never abort",
            "limitations": [],
        }
    )
    grounded = ground_model_finding(hallucination, evidence)
    assert "unavailable (not zero)" in grounded.summary
    assert "not ready" in grounded.summary
    assert "120" not in grounded.summary
    assert grounded.confidence == "medium"
    assert "Three fresh successful requests" in grounded.expected_recovery
    assert "expired approval" in grounded.abort_conditions
    assert grounded.probable_cause.startswith("AI hypothesis (unverified):")
    assert any("not a restart schedule" in s for s in grounded.limitations)


def test_unknown_scenario_does_not_gain_confidence_from_model():
    from app.services.investigation import ground_model_finding

    evidence = [{"id": "obs", "kind": "observation", "data": {"ready": None}}]
    finding = diagnose(evidence).model_copy(
        update={"confidence": "high", "recommended_action": "disable_failure"}
    )
    guarded = ground_model_finding(finding, evidence)
    assert guarded.confidence == "low"
    assert guarded.recommended_action == "investigate_more"
    assert "readiness unavailable" in guarded.summary


def test_model_list_items_are_bounded():
    finding = diagnose([{"id": "obs", "kind": "observation", "data": {}}]).model_dump()
    finding["alternatives"] = ["x" * 701]
    with pytest.raises(ValueError):
        validate_finding(finding, [{"id": "obs"}])

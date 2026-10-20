import time
import httpx
import pytest
from fastapi.testclient import TestClient
from demo import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEMO_CONTROL_TOKEN", "test-token")
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"status": "paid"})
    )
    return TestClient(create_app("checkout", transport))


def activate(client, name, duration=30):
    return client.post(
        "/control/scenario",
        headers={"X-Demo-Token": "test-token"},
        json={"name": name, "duration_seconds": duration},
    )


def test_baseline(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    response = client.post("/api/checkout", json={"product_id": "book"})
    assert response.status_code == 201
    assert response.headers["X-Request-ID"]
    assert client.get("/api/orders/" + response.json()["id"]).json()["status"] == "paid"
    assert (
        'demo_requests_total{route="/api/checkout",service="checkout",status="201"} 1.0'
        in client.get("/metrics").text
    )


@pytest.mark.parametrize(
    "scenario,status",
    [
        ("errors", 503),
        ("database", 503),
        ("deployment", 503),
        ("dependency_timeout", 504),
        ("cpu", 201),
        ("memory", 201),
        ("latency", 201),
    ],
)
def test_failures_and_recovery(client, scenario, status):
    assert activate(client, scenario).status_code == 200
    started = time.perf_counter()
    assert (
        client.post("/api/checkout", json={"product_id": "mug"}).status_code == status
    )
    if scenario == "latency":
        # Windows timer granularity can wake asyncio sleep slightly early.
        assert time.perf_counter() - started >= 0.28
    activate(client, "healthy")
    assert client.get("/ready").status_code == 200
    assert client.post("/api/checkout", json={"product_id": "mug"}).status_code == 201


def test_controls(client):
    assert client.post("/control/scenario", json={"name": "errors"}).status_code == 403
    assert activate(client, "arbitrary-command").status_code == 422
    assert activate(client, "errors", 121).status_code == 422
    assert activate(client, "errors", 0).status_code == 422


def test_expiry(client):
    activate(client, "errors", 1)
    time.sleep(1.05)
    assert client.get("/ready").status_code == 200


def test_dependency_failure(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    client = TestClient(create_app("checkout", transport))
    assert client.post("/api/checkout", json={"product_id": "book"}).status_code == 502
    assert "demo_dependency_failures_total 1.0" in client.get("/metrics").text


def test_validation(client):
    assert (
        client.post(
            "/api/checkout", json={"product_id": "book", "quantity": 100}
        ).status_code
        == 422
    )
    assert client.get("/api/orders/missing").status_code == 404


def test_missing_control_configuration(client, monkeypatch):
    monkeypatch.delenv("DEMO_CONTROL_TOKEN")
    assert activate(client, "errors").status_code == 403
    assert client.get("/control/scenario").status_code == 403


def test_wrong_control_token(client):
    response = client.post(
        "/control/scenario", headers={"X-Demo-Token": "wrong"}, json={"name": "errors"}
    )
    assert response.status_code == 403
    assert client.get("/ready").status_code == 200


def test_unknown_paths_do_not_expand_metric_labels(client):
    client.get("/unknown/one")
    client.get("/unknown/two")
    metrics = client.get("/metrics").text
    assert "unknown/one" not in metrics
    assert 'route="unmatched"' in metrics


def test_non_ascii_control_token(client):
    response = client.post(
        "/control/scenario",
        headers=[(b"X-Demo-Token", b"\xc3\xa9")],
        json={"name": "errors"},
    )
    assert response.status_code == 403


def test_real_trace_correlation_and_bounded_evidence(client):
    response = client.post("/api/checkout", json={"product_id": "book"})
    trace_id = response.headers["X-Trace-ID"]
    assert len(trace_id) == 32 and int(trace_id, 16) != 0
    result = client.get(
        "/control/evidence", headers={"X-Demo-Token": "test-token"}
    ).json()
    assert any(span["trace_id"] == trace_id for span in result["traces"])
    assert any(log["trace_id"] == trace_id for log in result["logs"])
    assert "test-token" not in str(result)


def test_revision_precondition_prevents_stale_change(client):
    state = client.get(
        "/control/scenario", headers={"X-Demo-Token": "test-token"}
    ).json()
    activate(client, "errors")
    response = client.post(
        "/control/scenario",
        headers={"X-Demo-Token": "test-token"},
        json={"name": "healthy", "expected_revision": state["revision"]},
    )
    assert response.status_code == 409
    assert client.get("/ready").status_code == 503


def test_restart_disabled_by_default(client):
    state = client.get(
        "/control/scenario", headers={"X-Demo-Token": "test-token"}
    ).json()
    response = client.post(
        "/control/restart",
        headers={"X-Demo-Token": "test-token"},
        json={
            "expected_revision": state["revision"],
            "expected_boot_id": state["boot_id"],
        },
    )
    assert response.status_code == 409


def test_restart_is_authorized_bound_and_claimed_once(monkeypatch):
    monkeypatch.setenv("DEMO_CONTROL_TOKEN", "test-token")
    monkeypatch.setenv("DEMO_RESTART_ENABLED", "true")
    exits = []
    client = TestClient(
        create_app("checkout", restart_callback=lambda: exits.append(True))
    )
    headers = {"X-Demo-Token": "test-token"}
    state = client.get("/control/scenario", headers=headers).json()
    body = {
        "expected_revision": state["revision"],
        "expected_boot_id": state["boot_id"],
    }
    assert client.post("/control/restart", json=body).status_code == 403
    assert (
        client.post("/control/restart", headers=headers, json=body).status_code == 409
    )
    original = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: original() + 11)
    assert (
        client.post(
            "/control/restart",
            headers=headers,
            json=body | {"expected_boot_id": "stale"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/control/restart", headers=headers, json=body | {"command": "anything"}
        ).status_code
        == 422
    )
    assert (
        client.post("/control/restart", headers=headers, json=body).status_code == 202
    )
    assert (
        client.post("/control/restart", headers=headers, json=body).status_code == 409
    )
    assert activate(client, "errors").status_code == 409
    assert exits == [True]


def test_demo_rollback_requires_recorded_version_and_rejects_replay(client):
    headers = {"X-Demo-Token": "test-token"}
    activate(client, "deployment")
    state = client.get("/control/scenario", headers=headers).json()
    assert (
        state["deployment_version"] == "demo-v2"
        and state["previous_version"] == "demo-v1"
    )
    assert client.post("/api/checkout", json={"product_id": "book"}).status_code == 503
    body = {
        "expected_revision": state["revision"],
        "expected_version": "demo-v2",
        "target_version": "demo-v1",
    }
    assert client.post("/control/rollback", json=body).status_code == 403
    assert (
        client.post(
            "/control/rollback",
            headers=headers,
            json=body | {"target_version": "arbitrary-image"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/control/rollback",
            headers=headers,
            json=body | {"expected_revision": "stale"},
        ).status_code
        == 409
    )
    assert (
        client.post("/control/rollback", headers=headers, json=body).json()["version"]
        == "demo-v1"
    )
    assert client.post("/api/checkout", json={"product_id": "book"}).status_code == 201
    assert (
        client.post("/control/rollback", headers=headers, json=body).status_code == 409
    )
    assert any(
        e["type"] == "demo_release_rolled_back"
        for e in client.get("/control/evidence", headers=headers).json()["changes"]
    )

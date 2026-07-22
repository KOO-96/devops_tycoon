"""API tests: session lifecycle, commands, snapshot, errors."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create(client: TestClient, seed: int = 42) -> str:
    r = client.post("/api/v1/game-sessions", json={"seed": seed, "users": 100})
    assert r.status_code == 201, r.text
    session_id: str = r.json()["session_id"]
    return session_id


def test_create_session(client: TestClient) -> None:
    r = client.post("/api/v1/game-sessions", json={"seed": 1})
    body = r.json()
    assert r.status_code == 201
    assert body["revision"] == 0
    assert body["current_tick"] == 0
    assert body["state_version"] == 2
    assert "X-Request-ID" in r.headers


def test_get_summary_and_snapshot(client: TestClient) -> None:
    sid = _create(client)
    summary = client.get(f"/api/v1/game-sessions/{sid}").json()
    assert summary["session_id"] == sid
    assert summary["current_tick"] == 0
    snap = client.get(f"/api/v1/game-sessions/{sid}/snapshot").json()
    assert snap["simulation_state_version"] == 2
    assert "snapshot" in snap


def test_missing_session_404(client: TestClient) -> None:
    r = client.get("/api/v1/game-sessions/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_command_applied_increments_revision_and_sequence(client: TestClient) -> None:
    sid = _create(client)
    r = client.post(
        f"/api/v1/game-sessions/{sid}/commands",
        json={
            "command_id": "c1",
            "command_type": "ADD_NODE",
            "payload": {"target": "lb", "node_kind": "load_balancer"},
        },
    )
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "APPLIED"
    assert body["sequence"] == 1
    assert body["session_revision"] == 1


def test_command_rejected_is_structured(client: TestClient) -> None:
    sid = _create(client)
    # DEPLOY to a non-existent server → simulation rejects (valid type, bad target).
    r = client.post(
        f"/api/v1/game-sessions/{sid}/commands",
        json={
            "command_id": "c1",
            "command_type": "DEPLOY",
            "payload": {"target": "ghost", "version": "v2"},
        },
    )
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "COMMAND_REJECTED"
    assert body["reason_code"] == "server_not_found"


def test_unknown_command_type_rejected(client: TestClient) -> None:
    sid = _create(client)
    r = client.post(
        f"/api/v1/game-sessions/{sid}/commands",
        json={"command_id": "c1", "command_type": "NOPE", "payload": {}},
    )
    # The discriminated union rejects an unknown command_type at the API boundary
    # (before the simulation) -> VALIDATION_ERROR.
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_revision_conflict(client: TestClient) -> None:
    sid = _create(client)
    r = client.post(
        f"/api/v1/game-sessions/{sid}/commands",
        json={
            "command_id": "c1",
            "command_type": "ADD_NODE",
            "payload": {"target": "lb", "node_kind": "load_balancer"},
            "expected_revision": 5,
        },
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "REVISION_CONFLICT"


def test_error_envelope_shape(client: TestClient) -> None:
    r = client.get("/api/v1/game-sessions/missing")
    err = r.json()["error"]
    assert set(err.keys()) == {"code", "message", "details", "request_id"}
    assert err["request_id"]

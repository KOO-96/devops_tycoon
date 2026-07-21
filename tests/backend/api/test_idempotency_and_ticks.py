"""API tests: idempotency, revision, strict tick validation, events."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _create(client: TestClient) -> str:
    session_id: str = client.post("/api/v1/game-sessions", json={"seed": 7}).json()["session_id"]
    return session_id


def _cmd(client: TestClient, sid: str, cid: str, payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = client.post(
        f"/api/v1/game-sessions/{sid}/commands",
        json={"command_id": cid, "command_type": "ADD_NODE", "payload": payload},
    ).json()
    return result


def test_same_id_same_payload_replays_stored_result(client: TestClient) -> None:
    sid = _create(client)
    p = {"target": "lb", "node_kind": "load_balancer"}
    first = _cmd(client, sid, "c1", p)
    second = _cmd(client, sid, "c1", p)
    assert first["sequence"] == second["sequence"] == 1
    # Revision did not advance again (no re-run).
    assert first["session_revision"] == second["session_revision"] == 1


def test_stale_revision_idempotent_retry_returns_stored_result(client: TestClient) -> None:
    # HIGH-1: idempotency lookup must precede the revision check.
    sid = _create(client)
    p = {"target": "lb", "node_kind": "load_balancer"}
    first = client.post(
        f"/api/v1/game-sessions/{sid}/commands",
        json={"command_id": "A", "command_type": "ADD_NODE", "payload": p, "expected_revision": 0},
    ).json()
    assert first["session_revision"] == 1
    # Retry with the ORIGINAL (now stale) expected_revision -> stored result, not conflict.
    retry = client.post(
        f"/api/v1/game-sessions/{sid}/commands",
        json={"command_id": "A", "command_type": "ADD_NODE", "payload": p, "expected_revision": 0},
    )
    assert retry.status_code == 200
    body = retry.json()
    assert body["sequence"] == first["sequence"]
    assert body["session_revision"] == first["session_revision"] == 1


def test_same_command_id_across_sessions_is_independent(client: TestClient) -> None:
    # HIGH-3: command_id is a per-session idempotency key; two sessions may reuse it.
    a = _create(client)
    b = _create(client)
    p = {"target": "lb", "node_kind": "load_balancer"}
    ra = _cmd(client, a, "shared", p)
    rb = _cmd(client, b, "shared", p)
    assert ra["status"] == rb["status"] == "APPLIED"
    assert ra["session_revision"] == rb["session_revision"] == 1
    # Per-session idempotent retry returns each session's own stored result.
    ra2 = _cmd(client, a, "shared", p)
    assert ra2["sequence"] == ra["sequence"]
    # Different payload for the same command_id conflicts only within its session.
    conflict = client.post(
        f"/api/v1/game-sessions/{a}/commands",
        json={
            "command_id": "shared",
            "command_type": "ADD_NODE",
            "payload": {"target": "lb2", "node_kind": "load_balancer"},
        },
    )
    assert conflict.status_code == 409
    # Session B's "shared" record is unaffected.
    assert client.get(f"/api/v1/game-sessions/{b}").json()["revision"] == 1


def test_same_id_different_command_type_conflicts(client: TestClient) -> None:
    # Same command_id + same payload but different command_type -> IDEMPOTENCY_CONFLICT.
    sid = _create(client)
    client.post(
        f"/api/v1/game-sessions/{sid}/commands",
        json={"command_id": "c1", "command_type": "PAUSE", "payload": {"paused": True}},
    )
    r = client.post(
        f"/api/v1/game-sessions/{sid}/commands",
        json={"command_id": "c1", "command_type": "SET_SPEED", "payload": {"paused": True}},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_same_id_different_payload_conflicts(client: TestClient) -> None:
    sid = _create(client)
    _cmd(client, sid, "c1", {"target": "lb", "node_kind": "load_balancer"})
    r = client.post(
        f"/api/v1/game-sessions/{sid}/commands",
        json={
            "command_id": "c1",
            "command_type": "ADD_NODE",
            "payload": {"target": "lb2", "node_kind": "load_balancer"},
        },
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_ticks_strict_validation(client: TestClient) -> None:
    sid = _create(client)
    base = f"/internal/v1/game-sessions/{sid}/advance"
    assert client.post(base, json={"ticks": True}).status_code == 422
    assert client.post(base, json={"ticks": False}).status_code == 422
    assert client.post(base, json={"ticks": -1}).status_code == 422
    assert client.post(base, json={"ticks": "1"}).status_code == 422
    assert client.post(base, json={"ticks": 0}).status_code == 200
    assert client.post(base, json={"ticks": 50}).status_code == 200
    # max_ticks_per_request is 50 in test settings.
    r = client.post(base, json={"ticks": 51})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_manual_tick_disabled(client: TestClient) -> None:
    # A second app with the manual API disabled.
    from backend.app import create_app
    from backend.config import Settings

    app = create_app(
        Settings(storage_backend="memory", event_broker="memory", enable_manual_tick_api=False)
    )
    with TestClient(app) as c:
        sid = c.post("/api/v1/game-sessions", json={"seed": 1}).json()["session_id"]
        r = c.post(f"/internal/v1/game-sessions/{sid}/advance", json={"ticks": 1})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "MANUAL_TICK_DISABLED"


def test_event_cursor_and_isolation(client: TestClient) -> None:
    sid_a = _create(client)
    sid_b = _create(client)
    _cmd(client, sid_a, "a1", {"target": "lb", "node_kind": "load_balancer"})
    client.post(f"/internal/v1/game-sessions/{sid_a}/advance", json={"ticks": 3})

    events_a = client.get(f"/api/v1/game-sessions/{sid_a}/events?after_cursor=0").json()["events"]
    cursors = [e["cursor"] for e in events_a]
    assert cursors == sorted(cursors)
    assert len(set(cursors)) == len(cursors)  # unique
    assert all(e["session_id"] == sid_a for e in events_a)

    # Session B has no events; isolation holds.
    events_b = client.get(f"/api/v1/game-sessions/{sid_b}/events").json()["events"]
    assert events_b == []

    # after_cursor paging returns only newer events.
    if cursors:
        mid = cursors[len(cursors) // 2]
        newer = client.get(f"/api/v1/game-sessions/{sid_a}/events?after_cursor={mid}").json()[
            "events"
        ]
        assert all(e["cursor"] > mid for e in newer)

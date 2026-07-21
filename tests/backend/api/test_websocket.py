"""WebSocket tests: connect, replay-on-connect, missing session error."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create(client: TestClient) -> str:
    session_id: str = client.post("/api/v1/game-sessions", json={"seed": 3}).json()["session_id"]
    return session_id


def test_connect_receives_session_state(client: TestClient) -> None:
    sid = _create(client)
    with client.websocket_connect(f"/ws/v1/game-sessions/{sid}") as ws:
        msg = ws.receive_json()
        assert msg["message_type"] == "SESSION_STATE"
        assert msg["session_id"] == sid
        assert msg["protocol_version"] == 1


def test_replay_after_cursor(client: TestClient) -> None:
    sid = _create(client)
    client.post(
        f"/api/v1/game-sessions/{sid}/commands",
        json={
            "command_id": "c1",
            "command_type": "ADD_NODE",
            "payload": {"target": "lb", "node_kind": "load_balancer"},
        },
    )
    client.post(f"/internal/v1/game-sessions/{sid}/advance", json={"ticks": 2})

    with client.websocket_connect(f"/ws/v1/game-sessions/{sid}?after_cursor=0") as ws:
        # Replayed domain events arrive before the final SESSION_STATE.
        seen_events = 0
        while True:
            msg = ws.receive_json()
            if msg["message_type"] == "DOMAIN_EVENT":
                seen_events += 1
                assert msg["cursor"] > 0
            elif msg["message_type"] == "SESSION_STATE":
                break
        assert seen_events > 0


def test_missing_session_sends_error_and_closes(client: TestClient) -> None:
    with client.websocket_connect("/ws/v1/game-sessions/missing") as ws:
        msg = ws.receive_json()
        assert msg["message_type"] == "ERROR"
        assert msg["payload"]["code"] == "SESSION_NOT_FOUND"

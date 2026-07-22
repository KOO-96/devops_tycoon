"""Real PG+Redis WebSocket integration: replay/live race, dedup, multi-connection."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, cast

import pytest
from backend.config import Settings
from backend.dependencies import Services
from backend.websocket.manager import handle_connection
from starlette.websockets import WebSocket, WebSocketDisconnect

from tests.backend.integration.conftest import LB_PAYLOAD, IntegrationHarness

pytestmark = pytest.mark.integration


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.closed = False
        self._disconnected = asyncio.Event()

    async def accept(self) -> None:
        pass

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self.closed = True

    async def receive_text(self) -> str:
        await self._disconnected.wait()
        raise WebSocketDisconnect(code=1000)

    def disconnect(self) -> None:
        self._disconnected.set()

    def domain_events(self) -> list[dict[str, Any]]:
        return [m for m in self.sent if m["message_type"] == "DOMAIN_EVENT"]

    def has_state(self) -> bool:
        return any(m["message_type"] == "SESSION_STATE" for m in self.sent)


class _BarrierEvents:
    """Wraps EventQueryService, blocking the first list_events (replay) on a gate."""

    def __init__(self, inner: Any, gate: asyncio.Event, hit: asyncio.Event) -> None:
        self._inner = inner
        self._gate = gate
        self._hit = hit
        self._first = True

    async def list_events(
        self, session_id: str, after_cursor: int, limit: int | None
    ) -> list[dict[str, Any]]:
        if self._first:
            self._first = False
            self._hit.set()
            await self._gate.wait()
        result: list[dict[str, Any]] = await self._inner.list_events(
            session_id, after_cursor=after_cursor, limit=limit
        )
        return result


def _services(harness: IntegrationHarness, events: Any) -> Services:
    return Services(
        settings=Settings(storage_backend="postgres", event_broker="redis"),
        session_service=harness.sessions,
        command_service=harness.commands,
        event_query_service=events,
        broker=harness.broker,
    )


async def _wait(cond: Any, timeout: float = 4.0) -> None:
    async def loop() -> None:
        while not cond():
            await asyncio.sleep(0.02)

    await asyncio.wait_for(loop(), timeout)


async def test_no_loss_or_dup_during_replay_race(harness: IntegrationHarness) -> None:
    sid = (await harness.sessions.create_session(seed=1))["session_id"]
    gate = asyncio.Event()
    hit = asyncio.Event()
    ws = FakeWS()
    svc = _services(harness, _BarrierEvents(harness.events, gate, hit))
    task = asyncio.create_task(handle_connection(cast("WebSocket", ws), sid, 0, svc))
    try:
        await asyncio.wait_for(hit.wait(), 4)  # replay reached; subscription already active
        # Commit an event WHILE replay is blocked.
        await harness.commands.apply_command(
            sid, command_id="X", command_type="ADD_NODE", payload=LB_PAYLOAD, expected_revision=None
        )
        gate.set()  # release replay
        await _wait(lambda: len(ws.domain_events()) >= 1)
        ids = [m["payload"]["event_id"] for m in ws.domain_events()]
        assert len(ids) == len(set(ids)), "event delivered more than once"
        assert len(ids) >= 1, "committed-during-replay event was lost"
    finally:
        ws.disconnect()
        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(task, 5)


async def test_multi_connection_and_cleanup(harness: IntegrationHarness) -> None:
    sid = (await harness.sessions.create_session(seed=1))["session_id"]
    other = (await harness.sessions.create_session(seed=2))["session_id"]
    ws1, ws2 = FakeWS(), FakeWS()
    svc = _services(harness, harness.events)
    t1 = asyncio.create_task(handle_connection(cast("WebSocket", ws1), sid, 0, svc))
    t2 = asyncio.create_task(handle_connection(cast("WebSocket", ws2), sid, 0, svc))
    try:
        await _wait(lambda: ws1.has_state() and ws2.has_state())
        await asyncio.sleep(0.2)  # ensure both in live mode

        await harness.commands.apply_command(
            sid,
            command_id="M1",
            command_type="ADD_NODE",
            payload=LB_PAYLOAD,
            expected_revision=None,
        )
        await _wait(lambda: ws1.domain_events() and ws2.domain_events())
        assert (
            ws1.domain_events()[0]["payload"]["event_id"]
            == ws2.domain_events()[0]["payload"]["event_id"]
        )

        # Close ws1; ws2 keeps receiving.
        ws1.disconnect()
        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(t1, 5)  # prompt shutdown (no 15s hang)
        before = len(ws2.domain_events())
        await harness.commands.apply_command(
            sid,
            command_id="M2",
            command_type="ADD_NODE",
            payload={"target": "app-1", "node_kind": "app_server"},
            expected_revision=None,
        )
        await _wait(lambda: len(ws2.domain_events()) > before)

        # Event from a different session is not delivered to ws2.
        await harness.commands.apply_command(
            other,
            command_id="O1",
            command_type="ADD_NODE",
            payload=LB_PAYLOAD,
            expected_revision=None,
        )
        await asyncio.sleep(0.3)
        assert all(m["session_id"] == sid for m in ws2.domain_events()), "cross-session leakage"
    finally:
        ws2.disconnect()
        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(t2, 5)

"""Real Redis integration: pub/sub, isolation, publish-order, durability."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import pytest
from backend.persistence.postgres import PgUnitOfWork

from tests.backend.integration.conftest import LB_PAYLOAD, IntegrationHarness

pytestmark = pytest.mark.integration


async def _recv(it: Any, timeout: float = 3.0) -> dict[str, Any] | None:
    try:
        return await asyncio.wait_for(anext(it), timeout=timeout)
    except (TimeoutError, StopAsyncIteration):
        return None


async def test_pubsub_roundtrip_and_isolation(harness: IntegrationHarness) -> None:
    sub_a = harness.broker.subscribe("sess-A")
    sub_b = harness.broker.subscribe("sess-B")
    async with sub_a as it_a, sub_b as it_b:
        await asyncio.sleep(0.2)  # allow SUBSCRIBE to activate
        await harness.broker.publish("sess-A", {"event_id": "e1", "cursor": 1})
        got_a = await _recv(it_a)
        got_b = await _recv(it_b, timeout=0.6)
        assert got_a is not None and got_a["event_id"] == "e1"
        assert got_b is None  # session B channel is isolated


async def test_multi_subscriber_same_session(harness: IntegrationHarness) -> None:
    s1 = harness.broker.subscribe("sess-X")
    s2 = harness.broker.subscribe("sess-X")
    async with s1 as it1, s2 as it2:
        await asyncio.sleep(0.2)
        await harness.broker.publish("sess-X", {"event_id": "e9", "cursor": 9})
        g1 = await _recv(it1)
        g2 = await _recv(it2)
        assert g1 and g2 and g1["event_id"] == g2["event_id"] == "e9"


async def test_publish_only_after_commit(
    harness: IntegrationHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid = (await harness.sessions.create_session(seed=1))["session_id"]
    sub = harness.broker.subscribe(sid)
    async with sub as it:
        # Continuously collect published messages (no mid-stream anext cancellation).
        collected: list[dict[str, Any]] = []

        async def collect() -> None:
            async for env in it:
                collected.append(env)

        collector = asyncio.create_task(collect())
        await asyncio.sleep(0.2)  # let SUBSCRIBE activate

        async def boom(self: PgUnitOfWork) -> None:
            raise RuntimeError("forced commit failure")

        monkeypatch.setattr(PgUnitOfWork, "commit", boom)
        with pytest.raises(RuntimeError):
            await harness.commands.apply_command(
                sid,
                command_id="F",
                command_type="ADD_NODE",
                payload=LB_PAYLOAD,
                expected_revision=None,
            )
        monkeypatch.undo()
        await asyncio.sleep(0.3)
        assert collected == [], "no publish on failed commit"

        # Successful commit publishes after commit.
        await harness.commands.apply_command(
            sid,
            command_id="OK",
            command_type="ADD_NODE",
            payload=LB_PAYLOAD,
            expected_revision=None,
        )
        await asyncio.sleep(0.4)
        collector.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await collector
        assert any(m.get("type") == "COMMAND_APPLIED" for m in collected)


async def test_publish_failure_keeps_db_and_allows_replay(
    harness: IntegrationHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid = (await harness.sessions.create_session(seed=1))["session_id"]

    async def failing_publish(session_id: str, envelope: dict[str, Any]) -> None:
        raise RuntimeError("redis down")

    monkeypatch.setattr(harness.broker, "publish", failing_publish)
    # Command still commits despite publish failure (transport is non-fatal).
    r = await harness.commands.apply_command(
        sid, command_id="P", command_type="ADD_NODE", payload=LB_PAYLOAD, expected_revision=None
    )
    assert r["session_revision"] == 1
    monkeypatch.undo()
    # Events are durable in PostgreSQL and recoverable via cursor replay.
    events = await harness.events.list_events(sid, after_cursor=0, limit=100)
    assert len(events) >= 1
    assert len({e["event_id"] for e in events}) == len(events)

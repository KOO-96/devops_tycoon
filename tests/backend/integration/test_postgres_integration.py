"""Real PostgreSQL integration: repository, concurrency, rollback, idempotency."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from backend.errors import ApiError, ErrorCode
from backend.persistence.postgres import PgUnitOfWork

from tests.backend.integration.conftest import LB_PAYLOAD, IntegrationHarness

pytestmark = pytest.mark.integration


async def test_repository_roundtrip_and_isolation(harness: IntegrationHarness) -> None:
    a = (await harness.sessions.create_session(seed=1))["session_id"]
    b = (await harness.sessions.create_session(seed=2))["session_id"]
    await harness.commands.apply_command(
        a, command_id="a1", command_type="ADD_NODE", payload=LB_PAYLOAD, expected_revision=0
    )
    snap = await harness.sessions.get_snapshot(a)
    assert snap["simulation_state_version"] == 2
    assert snap["revision"] == 1
    # Session B untouched and isolated.
    b_summary = await harness.sessions.get_summary(b)
    assert b_summary["revision"] == 0
    assert (await harness.events.list_events(b, after_cursor=0, limit=100)) == []


async def test_stale_revision_idempotent_retry_returns_stored_result(
    harness: IntegrationHarness,
) -> None:
    sid = (await harness.sessions.create_session(seed=1))["session_id"]
    r1 = await harness.commands.apply_command(
        sid, command_id="A", command_type="ADD_NODE", payload=LB_PAYLOAD, expected_revision=0
    )
    assert r1["session_revision"] == 1
    # Retry with the ORIGINAL (now stale) expected_revision -> stored result, no conflict.
    r2 = await harness.commands.apply_command(
        sid, command_id="A", command_type="ADD_NODE", payload=LB_PAYLOAD, expected_revision=0
    )
    assert r2["sequence"] == r1["sequence"]
    assert r2["session_revision"] == r1["session_revision"]
    summary = await harness.sessions.get_summary(sid)
    assert summary["revision"] == 1  # simulation ran once, no extra sequence/revision


async def test_same_id_different_payload_conflicts_over_stale_revision(
    harness: IntegrationHarness,
) -> None:
    sid = (await harness.sessions.create_session(seed=1))["session_id"]
    await harness.commands.apply_command(
        sid, command_id="A", command_type="ADD_NODE", payload=LB_PAYLOAD, expected_revision=0
    )
    with pytest.raises(ApiError) as exc:
        await harness.commands.apply_command(
            sid,
            command_id="A",
            command_type="ADD_NODE",
            payload={"target": "lb2", "node_kind": "load_balancer"},
            expected_revision=0,
        )
    assert exc.value.code == ErrorCode.IDEMPOTENCY_CONFLICT


async def test_concurrent_same_command_id_runs_once(harness: IntegrationHarness) -> None:
    sid = (await harness.sessions.create_session(seed=1))["session_id"]

    async def apply() -> dict[str, Any]:
        return await harness.commands.apply_command(
            sid,
            command_id="dup",
            command_type="ADD_NODE",
            payload=LB_PAYLOAD,
            expected_revision=None,
        )

    r1, r2 = await asyncio.gather(apply(), apply())
    assert r1["sequence"] == r2["sequence"] == 1
    summary = await harness.sessions.get_summary(sid)
    assert summary["revision"] == 1


async def test_concurrent_distinct_commands_unique_sequences(
    harness: IntegrationHarness,
) -> None:
    sid = (await harness.sessions.create_session(seed=1))["session_id"]

    async def apply(i: int) -> dict[str, Any]:
        return await harness.commands.apply_command(
            sid,
            command_id=f"c{i}",
            command_type="ADD_NODE",
            payload={"target": f"app-{i}", "node_kind": "app_server"},
            expected_revision=None,
        )

    results = await asyncio.gather(*[apply(i) for i in range(1, 9)])
    assert sorted(r["sequence"] for r in results) == list(range(1, 9))
    summary = await harness.sessions.get_summary(sid)
    assert summary["revision"] == 8


async def test_rollback_on_commit_failure_leaves_no_partial_state(
    harness: IntegrationHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid = (await harness.sessions.create_session(seed=1))["session_id"]

    async def boom(self: PgUnitOfWork) -> None:
        raise RuntimeError("forced commit failure")

    monkeypatch.setattr(PgUnitOfWork, "commit", boom)
    with pytest.raises(RuntimeError):
        await harness.commands.apply_command(
            sid, command_id="R", command_type="ADD_NODE", payload=LB_PAYLOAD, expected_revision=None
        )
    monkeypatch.undo()

    summary = await harness.sessions.get_summary(sid)
    assert summary["revision"] == 0
    assert (await harness.events.list_events(sid, after_cursor=0, limit=100)) == []
    # Subsequent command still works.
    ok = await harness.commands.apply_command(
        sid, command_id="R2", command_type="ADD_NODE", payload=LB_PAYLOAD, expected_revision=None
    )
    assert ok["session_revision"] == 1

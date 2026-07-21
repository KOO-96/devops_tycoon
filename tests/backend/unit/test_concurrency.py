"""Concurrency: per-session serialization at the application layer."""

from __future__ import annotations

import asyncio
from typing import Any

from tests.backend.conftest import ServiceHarness


async def test_concurrent_distinct_commands_get_unique_sequences(
    harness: ServiceHarness,
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

    results = await asyncio.gather(*[apply(i) for i in range(1, 11)])
    sequences = sorted(r["sequence"] for r in results)
    assert sequences == list(range(1, 11)), "sequences must be unique and gap-free"

    summary = await harness.sessions.get_summary(sid)
    assert summary["revision"] == 10, "no lost updates"


async def test_concurrent_same_command_id_runs_simulation_once(
    harness: ServiceHarness,
) -> None:
    sid = (await harness.sessions.create_session(seed=1))["session_id"]
    payload = {"target": "lb", "node_kind": "load_balancer"}

    async def apply() -> dict[str, Any]:
        return await harness.commands.apply_command(
            sid,
            command_id="dup",
            command_type="ADD_NODE",
            payload=payload,
            expected_revision=None,
        )

    r1, r2 = await asyncio.gather(apply(), apply())
    assert r1["sequence"] == r2["sequence"] == 1
    summary = await harness.sessions.get_summary(sid)
    assert summary["revision"] == 1, "duplicate command_id applied exactly once"

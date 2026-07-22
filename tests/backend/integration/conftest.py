"""Integration fixtures: real PostgreSQL + Redis.

Enabled only when both env vars are set (skipped otherwise):
    DEVOPS_TYCOON_TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
    DEVOPS_TYCOON_TEST_REDIS_URL=redis://host:port/0

Schema is created once per session via Alembic (not metadata.create_all), each
test truncates the tables (RESTART IDENTITY), and the session tears down via
alembic downgrade — alembic_version is never left stale (§10).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from backend.adapters.event_broker import RedisEventBroker
from backend.adapters.simulation_adapter import SimulationAdapter
from backend.application.command_service import CommandService
from backend.application.event_service import EventQueryService
from backend.application.game_session_service import GameSessionService
from backend.persistence.postgres import PgUnitOfWorkFactory, build_postgres_storage
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

_DB = os.environ.get("DEVOPS_TYCOON_TEST_DATABASE_URL")
_REDIS = os.environ.get("DEVOPS_TYCOON_TEST_REDIS_URL")
_ROOT = Path(__file__).resolve().parents[3]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (_DB and _REDIS),
        reason="requires DEVOPS_TYCOON_TEST_DATABASE_URL and DEVOPS_TYCOON_TEST_REDIS_URL",
    ),
]


@pytest.fixture(scope="session")
def pg_schema() -> Iterator[None]:
    assert _DB is not None

    async def reset() -> None:
        engine = create_async_engine(_DB)
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await engine.dispose()

    asyncio.run(reset())
    env = {**os.environ, "DEVOPS_TYCOON_DATABASE_URL": _DB}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], check=True, cwd=_ROOT, env=env
    )
    yield
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"], check=True, cwd=_ROOT, env=env
    )


@pytest.fixture
async def clean_tables(pg_schema: None) -> AsyncIterator[None]:
    assert _DB is not None
    engine = create_async_engine(_DB)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE game_events, game_commands, game_sessions RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()
    yield


@dataclass
class IntegrationHarness:
    factory: PgUnitOfWorkFactory
    broker: RedisEventBroker
    sessions: GameSessionService
    commands: CommandService
    events: EventQueryService


@pytest.fixture
async def harness(clean_tables: None) -> AsyncIterator[IntegrationHarness]:
    assert _DB is not None and _REDIS is not None
    factory, _ping = build_postgres_storage(_DB)
    broker = RedisEventBroker(_REDIS)
    adapter = SimulationAdapter()
    h = IntegrationHarness(
        factory=factory,
        broker=broker,
        sessions=GameSessionService(factory, adapter),
        commands=CommandService(factory, adapter, broker),
        events=EventQueryService(factory, default_limit=100, max_limit=1000),
    )
    yield h
    await factory.aclose()
    await broker._client.aclose()  # noqa: SLF001 - test teardown


LB_PAYLOAD: dict[str, Any] = {"target": "lb", "node_kind": "load_balancer"}

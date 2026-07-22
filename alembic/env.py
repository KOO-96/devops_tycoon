"""Alembic environment (async). Migrations are run by explicit ops command only.

The application never auto-migrates on startup.
"""

from __future__ import annotations

import asyncio
import os

from alembic import context
from backend.config import get_settings
from backend.persistence.models import Base
from sqlalchemy.ext.asyncio import create_async_engine

target_metadata = Base.metadata


def _database_url() -> str:
    return os.environ.get("DEVOPS_TYCOON_DATABASE_URL") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_database_url())
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

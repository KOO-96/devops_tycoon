"""PostgreSQL integration tests (require a real database).

Run with: DEVOPS_TYCOON_TEST_DATABASE_URL=postgresql+asyncpg://... pytest -m integration
These are skipped by default (no DB in the unit/API environment).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

_DB_URL = os.environ.get("DEVOPS_TYCOON_TEST_DATABASE_URL")


@pytest.mark.skipif(_DB_URL is None, reason="no test PostgreSQL configured")
async def test_session_roundtrip_and_row_lock() -> None:  # pragma: no cover - integration
    from backend.persistence.models import Base
    from backend.persistence.postgres import build_postgres_storage

    factory, _ping = build_postgres_storage(_DB_URL)  # type: ignore[arg-type]
    engine = factory._engine  # noqa: SLF001 - test setup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        # Placeholder for real create/lock/commit assertions against PostgreSQL.
        assert factory is not None
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await factory.aclose()

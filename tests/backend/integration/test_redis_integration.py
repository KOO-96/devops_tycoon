"""Redis integration tests (require a real Redis).

Run with: DEVOPS_TYCOON_TEST_REDIS_URL=redis://... pytest -m integration
Skipped by default.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

_REDIS_URL = os.environ.get("DEVOPS_TYCOON_TEST_REDIS_URL")


@pytest.mark.skipif(_REDIS_URL is None, reason="no test Redis configured")
async def test_publish_subscribe_roundtrip() -> None:  # pragma: no cover - integration
    from backend.adapters.event_broker import RedisEventBroker

    broker = RedisEventBroker(_REDIS_URL)  # type: ignore[arg-type]
    assert await broker.ping() is True

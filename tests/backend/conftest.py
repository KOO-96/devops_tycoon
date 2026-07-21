"""Shared backend test fixtures (in-memory storage + broker, no external services)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from backend.adapters.event_broker import InMemoryEventBroker
from backend.adapters.simulation_adapter import SimulationAdapter
from backend.app import create_app
from backend.application.command_service import CommandService
from backend.application.event_service import EventQueryService
from backend.application.game_session_service import GameSessionService
from backend.config import Settings
from backend.persistence.memory import MemoryStore, MemoryUnitOfWorkFactory
from fastapi.testclient import TestClient


def memory_settings() -> Settings:
    return Settings(
        storage_backend="memory",
        event_broker="memory",
        enable_manual_tick_api=True,
        max_ticks_per_request=50,
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(memory_settings())
    with TestClient(app) as test_client:
        yield test_client


class ServiceHarness:
    """Direct application-layer wiring for unit/concurrency tests."""

    def __init__(self) -> None:
        self.store = MemoryStore()
        self.factory = MemoryUnitOfWorkFactory(self.store)
        self.adapter = SimulationAdapter()
        self.broker = InMemoryEventBroker()
        self.sessions = GameSessionService(self.factory, self.adapter)
        self.commands = CommandService(self.factory, self.adapter, self.broker)
        self.events = EventQueryService(self.factory, default_limit=100, max_limit=1000)


@pytest.fixture
def harness() -> ServiceHarness:
    return ServiceHarness()

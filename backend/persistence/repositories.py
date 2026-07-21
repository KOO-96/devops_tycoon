"""Repository and Unit-of-Work protocols.

The application services depend only on these protocols, never on a concrete
backend. Correctness (per-session serialization, atomic commit) is guaranteed by
the UnitOfWork implementation: PostgreSQL uses a real transaction + row lock;
the in-memory backend uses a per-session lock held for the UoW lifetime.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.persistence.records import CommandRecord, EventRecord, SessionRecord


@runtime_checkable
class SessionRepository(Protocol):
    async def get(self, session_id: str) -> SessionRecord | None: ...
    async def get_for_update(self, session_id: str) -> SessionRecord | None: ...
    async def add(self, record: SessionRecord) -> None: ...
    async def update(self, record: SessionRecord) -> None: ...


@runtime_checkable
class CommandRepository(Protocol):
    async def get_by_command_id(self, session_id: str, command_id: str) -> CommandRecord | None: ...
    async def add(self, record: CommandRecord) -> None: ...


@runtime_checkable
class EventRepository(Protocol):
    async def append(self, records: list[EventRecord]) -> list[EventRecord]: ...
    async def list_after(
        self, session_id: str, after_cursor: int, limit: int
    ) -> list[EventRecord]: ...


@runtime_checkable
class UnitOfWork(Protocol):
    sessions: SessionRepository
    commands: CommandRepository
    events: EventRepository

    async def __aenter__(self) -> UnitOfWork: ...
    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    async def commit(self) -> None: ...


@runtime_checkable
class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...

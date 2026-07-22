"""In-memory persistence backend.

Default for local/dev/test (no external services). Correctness mirrors the
PostgreSQL backend: a per-session lock is acquired by ``get_for_update`` and held
until the UnitOfWork exits, serializing all state transitions for a session;
writes are buffered and applied atomically on ``commit`` (discarded on rollback).
"""

from __future__ import annotations

import asyncio
import copy
from datetime import UTC, datetime

from backend.persistence.records import CommandRecord, EventRecord, SessionRecord
from backend.persistence.repositories import (
    CommandRepository,
    EventRepository,
    SessionRepository,
)


def _now() -> datetime:
    return datetime.now(UTC)


class MemoryStore:
    """Process-wide committed state."""

    def __init__(self) -> None:
        self.sessions: dict[str, SessionRecord] = {}
        self.commands: dict[tuple[str, str], CommandRecord] = {}
        self.events: dict[str, list[EventRecord]] = {}
        self.cursors: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global = asyncio.Lock()

    def lock_for(self, session_id: str) -> asyncio.Lock:
        lock = self._locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[session_id] = lock
        return lock


class _SessionRepo:
    def __init__(self, uow: MemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, session_id: str) -> SessionRecord | None:
        rec = self._uow.store.sessions.get(session_id)
        return copy.deepcopy(rec) if rec is not None else None

    async def get_for_update(self, session_id: str) -> SessionRecord | None:
        await self._uow._acquire(session_id)
        rec = self._uow.store.sessions.get(session_id)
        return copy.deepcopy(rec) if rec is not None else None

    async def add(self, record: SessionRecord) -> None:
        self._uow._staged_sessions[record.id] = copy.deepcopy(record)

    async def update(self, record: SessionRecord) -> None:
        record.updated_at = _now()
        self._uow._staged_sessions[record.id] = copy.deepcopy(record)


class _CommandRepo:
    def __init__(self, uow: MemoryUnitOfWork) -> None:
        self._uow = uow

    async def get_by_command_id(self, session_id: str, command_id: str) -> CommandRecord | None:
        rec = self._uow.store.commands.get((session_id, command_id))
        return copy.deepcopy(rec) if rec is not None else None

    async def add(self, record: CommandRecord) -> None:
        self._uow._staged_commands.append(copy.deepcopy(record))


class _EventRepo:
    def __init__(self, uow: MemoryUnitOfWork) -> None:
        self._uow = uow

    async def append(self, records: list[EventRecord]) -> list[EventRecord]:
        # Cursors are finalized at commit; return the same objects so callers see
        # the assigned cursors afterward.
        self._uow._staged_events.extend(records)
        return records

    async def list_after(self, session_id: str, after_cursor: int, limit: int) -> list[EventRecord]:
        items = self._uow.store.events.get(session_id, [])
        out = [copy.deepcopy(e) for e in items if e.cursor > after_cursor]
        out.sort(key=lambda e: e.cursor)
        return out[:limit]


class MemoryUnitOfWork:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store
        self.sessions: SessionRepository = _SessionRepo(self)
        self.commands: CommandRepository = _CommandRepo(self)
        self.events: EventRepository = _EventRepo(self)
        self._staged_sessions: dict[str, SessionRecord] = {}
        self._staged_commands: list[CommandRecord] = []
        self._staged_events: list[EventRecord] = []
        self._locked_session: str | None = None
        self._committed = False

    async def _acquire(self, session_id: str) -> None:
        if self._locked_session == session_id:
            return
        if self._locked_session is not None:
            raise RuntimeError("MemoryUnitOfWork locks a single session per transaction")
        await self.store.lock_for(session_id).acquire()
        self._locked_session = session_id

    async def __aenter__(self) -> MemoryUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        try:
            if not self._committed:
                self._staged_sessions.clear()
                self._staged_commands.clear()
                self._staged_events.clear()
        finally:
            if self._locked_session is not None:
                self.store.lock_for(self._locked_session).release()
                self._locked_session = None

    async def commit(self) -> None:
        for sid, rec in self._staged_sessions.items():
            self.store.sessions[sid] = rec
        for cmd in self._staged_commands:
            self.store.commands[(cmd.session_id, cmd.command_id)] = cmd
        for ev in self._staged_events:
            cursor = self.store.cursors.get(ev.session_id, 0) + 1
            self.store.cursors[ev.session_id] = cursor
            ev.cursor = cursor
            if ev.created_at is None:
                ev.created_at = _now()
            self.store.events.setdefault(ev.session_id, []).append(copy.deepcopy(ev))
        self._committed = True


class MemoryUnitOfWorkFactory:
    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()

    def __call__(self) -> MemoryUnitOfWork:
        return MemoryUnitOfWork(self.store)

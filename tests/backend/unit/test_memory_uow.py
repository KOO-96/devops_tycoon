"""Unit tests for the in-memory UnitOfWork: rollback, commit, sequence policy."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.persistence.memory import MemoryStore, MemoryUnitOfWorkFactory
from backend.persistence.records import SessionRecord, SessionStatus


def _session(sid: str) -> SessionRecord:
    now = datetime.now(UTC)
    return SessionRecord(
        id=sid,
        status=SessionStatus.ACTIVE,
        simulation_state={"clock": {"tick": 0}},
        simulation_state_version=2,
        revision=0,
        next_command_sequence=1,
        created_at=now,
        updated_at=now,
    )


async def test_commit_persists() -> None:
    factory = MemoryUnitOfWorkFactory(MemoryStore())
    async with factory() as uow:
        await uow.sessions.add(_session("s1"))
        await uow.commit()
    async with factory() as uow:
        assert await uow.sessions.get("s1") is not None


async def test_rollback_discards_when_not_committed() -> None:
    store = MemoryStore()
    factory = MemoryUnitOfWorkFactory(store)
    async with factory() as uow:
        await uow.sessions.add(_session("s1"))
        # no commit -> rollback on exit
    async with factory() as uow:
        assert await uow.sessions.get("s1") is None


async def test_exception_rolls_back_and_releases_lock() -> None:
    store = MemoryStore()
    factory = MemoryUnitOfWorkFactory(store)
    async with factory() as uow:
        await uow.sessions.add(_session("s1"))
        await uow.commit()

    class Boom(Exception):
        pass

    try:
        async with factory() as uow:
            rec = await uow.sessions.get_for_update("s1")
            assert rec is not None
            rec.revision = 99
            await uow.sessions.update(rec)
            raise Boom
    except Boom:
        pass

    # Change discarded; lock released so a new UoW can proceed.
    async with factory() as uow:
        rec = await uow.sessions.get_for_update("s1")
        assert rec is not None
        assert rec.revision == 0


async def test_events_get_monotonic_cursors_on_commit() -> None:
    from backend.persistence.records import EventRecord

    store = MemoryStore()
    factory = MemoryUnitOfWorkFactory(store)
    async with factory() as uow:
        await uow.sessions.add(_session("s1"))
        await uow.commit()
    async with factory() as uow:
        await uow.sessions.get_for_update("s1")
        recs = [EventRecord(0, f"e{i}", "s1", 1, i, "CACHE_HIT", "") for i in range(3)]
        appended = await uow.events.append(recs)
        await uow.commit()
    cursors = [r.cursor for r in appended]
    assert cursors == [1, 2, 3]

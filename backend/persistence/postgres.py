"""PostgreSQL persistence backend (production).

Correctness source of truth: a real transaction per UnitOfWork with
``SELECT ... FOR UPDATE`` on the session row. Integration-tested against a real
PostgreSQL (see tests/backend/integration), not in unit/API runs.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.persistence.models import GameCommandModel, GameEventModel, GameSessionModel
from backend.persistence.records import (
    CommandRecord,
    CommandStatus,
    EventRecord,
    SessionRecord,
    SessionStatus,
)
from backend.persistence.repositories import (
    CommandRepository,
    EventRepository,
    SessionRepository,
)


def _session_to_record(m: GameSessionModel) -> SessionRecord:
    return SessionRecord(
        id=m.id,
        status=SessionStatus(m.status),
        simulation_state=m.simulation_state,
        simulation_state_version=m.simulation_state_version,
        revision=m.revision,
        next_command_sequence=m.next_command_sequence,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class _PgSessionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, session_id: str) -> SessionRecord | None:
        m = await self._session.get(GameSessionModel, session_id)
        return _session_to_record(m) if m is not None else None

    async def get_for_update(self, session_id: str) -> SessionRecord | None:
        stmt = select(GameSessionModel).where(GameSessionModel.id == session_id).with_for_update()
        m = (await self._session.execute(stmt)).scalar_one_or_none()
        return _session_to_record(m) if m is not None else None

    async def add(self, record: SessionRecord) -> None:
        self._session.add(
            GameSessionModel(
                id=record.id,
                status=record.status.value,
                simulation_state=record.simulation_state,
                simulation_state_version=record.simulation_state_version,
                revision=record.revision,
                next_command_sequence=record.next_command_sequence,
            )
        )

    async def update(self, record: SessionRecord) -> None:
        m = await self._session.get(GameSessionModel, record.id)
        if m is None:
            raise KeyError(record.id)
        m.status = record.status.value
        m.simulation_state = record.simulation_state
        m.simulation_state_version = record.simulation_state_version
        m.revision = record.revision
        m.next_command_sequence = record.next_command_sequence


class _PgCommandRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_command_id(self, session_id: str, command_id: str) -> CommandRecord | None:
        stmt = select(GameCommandModel).where(
            GameCommandModel.session_id == session_id,
            GameCommandModel.command_id == command_id,
        )
        m = (await self._session.execute(stmt)).scalar_one_or_none()
        if m is None:
            return None
        return CommandRecord(
            id=m.id,
            session_id=m.session_id,
            command_id=m.command_id,
            sequence=m.sequence,
            command_type=m.command_type,
            payload_hash=m.payload_hash,
            status=CommandStatus(m.status),
            result=m.result,
            created_at=m.created_at,
            completed_at=m.completed_at,
        )

    async def add(self, record: CommandRecord) -> None:
        self._session.add(
            GameCommandModel(
                id=record.id,
                session_id=record.session_id,
                command_id=record.command_id,
                sequence=record.sequence,
                command_type=record.command_type,
                payload_hash=record.payload_hash,
                status=record.status.value,
                result=record.result,
                completed_at=record.completed_at,
            )
        )


class _PgEventRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, records: list[EventRecord]) -> list[EventRecord]:
        models = [
            GameEventModel(
                event_id=r.event_id,
                session_id=r.session_id,
                session_revision=r.session_revision,
                tick=r.tick,
                event_type=r.event_type,
                target=r.target,
                payload=r.payload,
            )
            for r in records
        ]
        self._session.add_all(models)
        await self._session.flush()  # assigns identity cursors
        for record, model in zip(records, models, strict=True):
            record.cursor = model.cursor
        return records

    async def list_after(self, session_id: str, after_cursor: int, limit: int) -> list[EventRecord]:
        stmt = (
            select(GameEventModel)
            .where(
                GameEventModel.session_id == session_id,
                GameEventModel.cursor > after_cursor,
            )
            .order_by(GameEventModel.cursor.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            EventRecord(
                cursor=m.cursor,
                event_id=m.event_id,
                session_id=m.session_id,
                session_revision=m.session_revision,
                tick=m.tick,
                event_type=m.event_type,
                target=m.target,
                payload=m.payload,
                created_at=m.created_at,
            )
            for m in rows
        ]


class PgUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.sessions: SessionRepository = _PgSessionRepo(session)
        self.commands: CommandRepository = _PgCommandRepo(session)
        self.events: EventRepository = _PgEventRepo(session)
        self._committed = False

    async def __aenter__(self) -> PgUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        try:
            if not self._committed:
                await self._session.rollback()
        finally:
            await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()
        self._committed = True


class PgUnitOfWorkFactory:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    def __call__(self) -> PgUnitOfWork:
        return PgUnitOfWork(self._sessionmaker())

    async def aclose(self) -> None:
        await self._engine.dispose()


def build_postgres_storage(database_url: str) -> tuple[PgUnitOfWorkFactory, Any]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = PgUnitOfWorkFactory(engine)

    async def ping() -> bool:
        try:
            async with engine.connect() as conn:
                await conn.exec_driver_sql("SELECT 1")
            return True
        except Exception:  # noqa: BLE001 - readiness probe never raises
            return False

    return factory, ping

"""Event envelope construction, persistence-backed query, and post-commit publish."""

from __future__ import annotations

import uuid
from typing import Any

from backend.adapters.event_broker import EventBroker
from backend.errors import ApiError, ErrorCode
from backend.persistence.records import EventRecord
from backend.persistence.repositories import UnitOfWorkFactory


def new_event_records(
    session_id: str,
    session_revision: int,
    sim_events: list[dict[str, Any]],
) -> list[EventRecord]:
    """Wrap Simulation domain events with Backend transport identity."""
    records: list[EventRecord] = []
    for ev in sim_events:
        detail = ev.get("detail") or {}
        records.append(
            EventRecord(
                cursor=0,  # assigned at commit
                event_id=str(uuid.uuid4()),
                session_id=session_id,
                session_revision=session_revision,
                tick=int(ev.get("tick", 0)),
                event_type=str(ev.get("type", "")),
                target=str(ev.get("target", "")),
                payload=dict(detail),
            )
        )
    return records


def envelope(record: EventRecord) -> dict[str, Any]:
    return {
        "event_id": record.event_id,
        "cursor": record.cursor,
        "session_id": record.session_id,
        "session_revision": record.session_revision,
        "tick": record.tick,
        "type": record.event_type,
        "target": record.target or None,
        "payload": record.payload,
    }


async def publish_after_commit(
    broker: EventBroker, session_id: str, records: list[EventRecord]
) -> None:
    """Publish committed events; a broker failure never affects the transaction."""
    for record in records:
        try:
            await broker.publish(session_id, envelope(record))
        except Exception:  # noqa: BLE001 - transport failure is non-fatal (DB is truth)
            return


class EventQueryService:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, *, default_limit: int, max_limit: int
    ) -> None:
        self._uow_factory = uow_factory
        self._default_limit = default_limit
        self._max_limit = max_limit

    async def list_events(
        self, session_id: str, after_cursor: int, limit: int | None
    ) -> list[dict[str, Any]]:
        effective = self._default_limit if limit is None else min(limit, self._max_limit)
        async with self._uow_factory() as uow:
            session = await uow.sessions.get(session_id)
            if session is None:
                raise ApiError(ErrorCode.SESSION_NOT_FOUND, "Game session was not found.")
            records = await uow.events.list_after(session_id, after_cursor, effective)
        return [envelope(r) for r in records]

"""Command application and manual tick advance — the transactional core.

Ordering guarantees (contract §11/§13):
  lock session -> check revision -> idempotency -> allocate sequence ->
  run simulation -> persist snapshot+command+events (one transaction) ->
  commit -> publish. Publish never precedes commit; a retried command_id is
  replayed from the stored result without re-running the simulation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from backend.adapters.event_broker import EventBroker
from backend.adapters.simulation_adapter import SimulationAdapter
from backend.application.event_service import (
    envelope,
    new_event_records,
    publish_after_commit,
)
from backend.errors import ApiError, ErrorCode
from backend.persistence.records import CommandRecord, CommandStatus, SessionRecord
from backend.persistence.repositories import UnitOfWork, UnitOfWorkFactory


def _now() -> datetime:
    return datetime.now(UTC)


def _request_hash(command_type: str, payload: dict[str, Any]) -> str:
    """Idempotency hash over command_type + canonical payload only.

    Excludes expected_revision, request id, timestamps, and the backend-issued
    sequence, so the same logical command retried with a new expected_revision
    still hashes identically (HIGH-1). A different command_type with the same
    payload hashes differently -> IDEMPOTENCY_CONFLICT.
    """
    canonical = json.dumps(
        {"command_type": command_type, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _state_summary(state: dict[str, Any]) -> dict[str, Any]:
    clock = state.get("clock", {})
    economy = state.get("economy", {})
    return {
        "current_tick": clock.get("tick", 0),
        "cash": economy.get("cash"),
        "user_trust": state.get("user_trust"),
    }


class CommandService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        adapter: SimulationAdapter,
        broker: EventBroker,
    ) -> None:
        self._uow_factory = uow_factory
        self._adapter = adapter
        self._broker = broker

    async def apply_command(
        self,
        session_id: str,
        *,
        command_id: str,
        command_type: str,
        payload: dict[str, Any],
        expected_revision: int | None,
    ) -> dict[str, Any]:
        request_hash = _request_hash(command_type, payload)
        published: list[Any] = []
        async with self._uow_factory() as uow:
            session = await self._locked_session(uow, session_id)

            # Idempotency is checked BEFORE the revision check (HIGH-1): a retry of
            # a known command_id must return the stored result even if the caller's
            # expected_revision is now stale.
            existing = await uow.commands.get_by_command_id(session_id, command_id)
            if existing is not None:
                if existing.payload_hash != request_hash:
                    raise ApiError(
                        ErrorCode.IDEMPOTENCY_CONFLICT,
                        "command_id was already used with a different command/payload.",
                        details={"command_id": command_id},
                    )
                # Return the ORIGINAL stored result (no re-run, no revision check).
                return existing.result

            # New command only: now enforce optimistic revision.
            self._check_revision(session, expected_revision)

            sequence = session.next_command_sequence
            result = self._adapter.apply_command(
                session.simulation_state,
                command_id=command_id,
                command_type=command_type,
                payload=payload,
                sequence=sequence,
            )

            new_revision = session.revision + 1
            session.revision = new_revision
            session.simulation_state = result.state
            session.simulation_state_version = result.state_version
            session.next_command_sequence = sequence + 1

            event_records = new_event_records(session_id, new_revision, result.events)
            status = (
                CommandStatus.APPLIED
                if result.command_status == "APPLIED"
                else CommandStatus.COMMAND_REJECTED
            )
            response = {
                "command_id": command_id,
                "sequence": sequence,
                "status": status.value,
                "reason_code": result.reason_code,
                "session_revision": new_revision,
                "current_tick": result.tick,
                "events": [],  # filled after cursors are assigned at commit
                "state_summary": _state_summary(result.state),
            }

            await uow.commands.add(
                CommandRecord(
                    id=command_id,
                    session_id=session_id,
                    command_id=command_id,
                    sequence=sequence,
                    command_type=command_type,
                    payload_hash=request_hash,
                    status=status,
                    result=response,
                    created_at=_now(),
                    completed_at=_now(),
                )
            )
            await uow.sessions.update(session)
            appended = await uow.events.append(event_records)
            await uow.commit()
            published = appended
            response["events"] = [envelope(r) for r in appended]

        await publish_after_commit(self._broker, session_id, published)
        return response

    async def advance_session(
        self, session_id: str, *, ticks: int, expected_revision: int | None
    ) -> dict[str, Any]:
        published: list[Any] = []
        async with self._uow_factory() as uow:
            session = await self._locked_session(uow, session_id)
            self._check_revision(session, expected_revision)

            result = self._adapter.advance(session.simulation_state, ticks)
            new_revision = session.revision + 1
            session.revision = new_revision
            session.simulation_state = result.state
            session.simulation_state_version = result.state_version

            event_records = new_event_records(session_id, new_revision, result.events)
            await uow.sessions.update(session)
            appended = await uow.events.append(event_records)
            await uow.commit()
            published = appended
            response = {
                "session_revision": new_revision,
                "current_tick": result.tick,
                "events": [envelope(r) for r in appended],
                "state_summary": _state_summary(result.state),
            }
        await publish_after_commit(self._broker, session_id, published)
        return response

    async def _locked_session(self, uow: UnitOfWork, session_id: str) -> SessionRecord:
        session = await uow.sessions.get_for_update(session_id)
        if session is None:
            raise ApiError(ErrorCode.SESSION_NOT_FOUND, "Game session was not found.")
        return session

    @staticmethod
    def _check_revision(session: SessionRecord, expected_revision: int | None) -> None:
        if expected_revision is not None and expected_revision != session.revision:
            raise ApiError(
                ErrorCode.REVISION_CONFLICT,
                "Stale revision; reload the session and retry.",
                details={"expected": expected_revision, "actual": session.revision},
            )

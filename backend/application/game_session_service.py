"""Game session lifecycle: create, summary, full snapshot."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from backend.adapters.simulation_adapter import SimulationAdapter
from backend.errors import ApiError, ErrorCode
from backend.persistence.records import SessionRecord, SessionStatus
from backend.persistence.repositories import UnitOfWorkFactory


def _now() -> datetime:
    return datetime.now(UTC)


class GameSessionService:
    def __init__(self, uow_factory: UnitOfWorkFactory, adapter: SimulationAdapter) -> None:
        self._uow_factory = uow_factory
        self._adapter = adapter

    async def create_session(self, seed: int, users: int = 0) -> dict[str, Any]:
        initial = self._adapter.create_initial_state(seed=seed, users=users)
        session_id = str(uuid.uuid4())
        # Stamp the simulation_id into the stored snapshot for traceability.
        initial.state["simulation_id"] = session_id
        now = _now()
        record = SessionRecord(
            id=session_id,
            status=SessionStatus.ACTIVE,
            simulation_state=initial.state,
            simulation_state_version=initial.state_version,
            revision=0,
            next_command_sequence=1,
            created_at=now,
            updated_at=now,
        )
        async with self._uow_factory() as uow:
            await uow.sessions.add(record)
            await uow.commit()
        return {
            "session_id": session_id,
            "status": record.status.value,
            "revision": record.revision,
            "current_tick": initial.tick,
            "state_version": record.simulation_state_version,
            "created_at": now.isoformat(),
        }

    async def get_summary(self, session_id: str) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            record = await uow.sessions.get(session_id)
        if record is None:
            raise ApiError(ErrorCode.SESSION_NOT_FOUND, "Game session was not found.")
        state = record.simulation_state
        clock = state.get("clock", {})
        economy = state.get("economy", {})
        incidents = state.get("incidents", {}).get("active", {})
        return {
            "session_id": record.id,
            "status": record.status.value,
            "revision": record.revision,
            "current_tick": clock.get("tick", 0),
            "speed": clock.get("speed", 1),
            "paused": clock.get("paused", False),
            "economy": {
                "cash": economy.get("cash"),
                "revenue_total": economy.get("revenue_total"),
                "cost_total": economy.get("cost_total"),
            },
            "user_trust": state.get("user_trust"),
            "investor_trust": state.get("investor_trust"),
            "active_incidents": [
                {"type": inc.get("type"), "target": inc.get("target"), "phase": inc.get("phase")}
                for inc in incidents.values()
            ],
            "updated_at": record.updated_at.isoformat(),
        }

    async def get_snapshot(self, session_id: str) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            record = await uow.sessions.get(session_id)
        if record is None:
            raise ApiError(ErrorCode.SESSION_NOT_FOUND, "Game session was not found.")
        return {
            "session_id": record.id,
            "revision": record.revision,
            "simulation_state_version": record.simulation_state_version,
            "snapshot": record.simulation_state,
        }

"""Adapter between Backend and the pure Simulation domain.

Backend never touches Simulation internals directly — only this adapter does. It
converts Backend command schemas to Simulation commands, runs `step`, restores
snapshots, and maps Simulation exceptions to the API error contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulation.commands import Command, CommandType
from simulation.errors import UnsupportedStateVersionError
from simulation.factory import new_config, new_state
from simulation.serialization import state_from_json, state_to_json
from simulation.state import STATE_VERSION, GameState

from backend.errors import ApiError, ErrorCode
from simulation import step


@dataclass
class AdapterResult:
    state: dict[str, Any]
    state_version: int
    tick: int
    events: list[dict[str, Any]] = field(default_factory=list)
    # Present for command application (None for plain advance).
    command_status: str | None = None
    reason_code: str | None = None


class SimulationAdapter:
    """Stateless translation layer over `simulation`."""

    def create_initial_state(self, seed: int, users: int = 0) -> AdapterResult:
        state = new_state(simulation_id="", seed=seed, users=users)
        return AdapterResult(
            state=self._dump(state),
            state_version=state.version,
            tick=state.clock.tick,
        )

    def restore(self, snapshot: dict[str, Any]) -> GameState:
        try:
            return GameState.from_dict(snapshot)
        except UnsupportedStateVersionError as exc:
            raise ApiError(
                ErrorCode.SNAPSHOT_VERSION_UNSUPPORTED,
                "Stored snapshot version is not supported by this server.",
                details={"expected": exc.expected, "received": exc.received},
            ) from exc

    def apply_command(
        self,
        snapshot: dict[str, Any],
        *,
        command_id: str,
        command_type: str,
        payload: dict[str, Any],
        sequence: int,
    ) -> AdapterResult:
        state = self.restore(snapshot)
        try:
            sim_type = CommandType(command_type)
        except ValueError as exc:
            raise ApiError(
                ErrorCode.COMMAND_REJECTED,
                "Unknown command type.",
                details={"command_type": command_type},
            ) from exc
        command = Command(
            id=command_id,
            type=sim_type,
            target=str(payload.get("target", "")),
            payload={k: v for k, v in payload.items() if k != "target"},
            sequence=sequence,
        )
        result = self._run(state, [command], ticks=0)
        status, reason = self._command_outcome(result.events, command_id)
        return AdapterResult(
            state=self._dump(result.state),
            state_version=result.state.version,
            tick=result.state.clock.tick,
            events=[e.to_dict() for e in result.events],
            command_status=status,
            reason_code=reason,
        )

    def advance(self, snapshot: dict[str, Any], ticks: int) -> AdapterResult:
        state = self.restore(snapshot)
        result = self._run(state, [], ticks=ticks)
        return AdapterResult(
            state=self._dump(result.state),
            state_version=result.state.version,
            tick=result.state.clock.tick,
            events=[e.to_dict() for e in result.events],
        )

    # -- internals --------------------------------------------------------

    def _run(self, state: GameState, commands: list[Command], *, ticks: int):  # type: ignore[no-untyped-def]
        try:
            return step(state, commands, new_config(), ticks=ticks)
        except ValueError as exc:
            raise ApiError(
                ErrorCode.VALIDATION_ERROR,
                "Invalid simulation input.",
                details={"reason": str(exc)},
            ) from exc
        except Exception as exc:  # noqa: BLE001 - convert any sim fault to a stable code
            raise ApiError(
                ErrorCode.SIMULATION_EXECUTION_FAILED,
                "Simulation execution failed.",
            ) from exc

    @staticmethod
    def _command_outcome(events: list[Any], command_id: str) -> tuple[str, str | None]:
        for event in events:
            detail = event.detail or {}
            if detail.get("command_id") != command_id:
                continue
            if event.type.value == "COMMAND_APPLIED":
                return "APPLIED", None
            if event.type.value == "COMMAND_REJECTED":
                return "COMMAND_REJECTED", str(detail.get("reason", "rejected"))
        # No explicit outcome event (handler applied silently): treat as applied.
        return "APPLIED", None

    @staticmethod
    def _dump(state: GameState) -> dict[str, Any]:
        # Round-trip through JSON to guarantee JSON-safe, NaN/Inf-free content.
        return state_from_json(state_to_json(state)).to_dict()

    @property
    def state_version(self) -> int:
        return STATE_VERSION

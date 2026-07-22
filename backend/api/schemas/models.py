"""API request/response schemas.

`StrictInt` is used for `ticks`, `seed`, and `expected_revision` so that Python's
`bool` (a subtype of `int`) and string inputs are rejected at the API boundary
(SIM-FU-001).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, StrictInt

from backend.errors import ErrorCode

_UUID: dict[str, Any] = {"format": "uuid"}
_DATETIME: dict[str, Any] = {"format": "date-time"}


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class CommandStatus(StrEnum):
    """Stable outcome of a command application (branch on this, not `message`)."""

    APPLIED = "APPLIED"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    DUPLICATE_COMMAND_ID = "DUPLICATE_COMMAND_ID"
    COMMAND_OUT_OF_ORDER = "COMMAND_OUT_OF_ORDER"
    COMMAND_REJECTED = "COMMAND_REJECTED"


class ReasonCode(StrEnum):
    """Stable `reason_code` values emitted with COMMAND_REJECTED.

    Mirrors the reasons produced by the simulation command handlers
    (`simulation.commands`) plus the adapter fallback. New values are added via a
    contract version bump, never left as a free string.
    """

    DUPLICATE_COMMAND_ID = "duplicate_command_id"
    ALREADY_APPLIED = "already_applied"
    COMMAND_OUT_OF_ORDER = "command_out_of_order"
    UNKNOWN_COMMAND_TYPE = "unknown_command_type"
    INVALID_OR_DUPLICATE_NODE_ID = "invalid_or_duplicate_node_id"
    UNKNOWN_NODE_KIND = "unknown_node_kind"
    NODE_NOT_FOUND = "node_not_found"
    MISSING_NODE = "missing_node"
    CONNECTION_NOT_ALLOWED = "connection_not_allowed"
    ALREADY_CONNECTED = "already_connected"
    NOT_CONNECTED = "not_connected"
    LB_NOT_FOUND = "lb_not_found"
    INVALID_ALGORITHM = "invalid_algorithm"
    SERVER_NOT_FOUND = "server_not_found"
    CACHE_NOT_FOUND = "cache_not_found"
    DB_NOT_FOUND = "db_not_found"
    MISSING_TARGET_VERSION = "missing_target_version"
    INVALID_SPEED = "invalid_speed"
    REJECTED = "rejected"


class CreateSessionRequest(BaseModel):
    seed: StrictInt = 0
    users: StrictInt = Field(default=0, ge=0)


class CreateSessionResponse(BaseModel):
    session_id: str = Field(json_schema_extra=_UUID)
    status: str
    revision: int
    current_tick: int
    state_version: int
    created_at: str = Field(json_schema_extra=_DATETIME)


class EconomySummary(BaseModel):
    cash: float | None = None
    revenue_total: float | None = None
    cost_total: float | None = None


class IncidentSummary(BaseModel):
    type: str | None = None
    target: str | None = None
    phase: str | None = None


class SessionSummaryResponse(BaseModel):
    session_id: str = Field(json_schema_extra=_UUID)
    status: str
    revision: int
    current_tick: int
    speed: int
    paused: bool
    economy: EconomySummary
    user_trust: float | None = None
    investor_trust: float | None = None
    active_incidents: list[IncidentSummary]
    updated_at: str = Field(json_schema_extra=_DATETIME)


class SnapshotResponse(BaseModel):
    session_id: str = Field(json_schema_extra=_UUID)
    revision: int
    simulation_state_version: int
    snapshot: dict[str, Any]


class EventEnvelope(BaseModel):
    event_id: str = Field(json_schema_extra=_UUID)
    cursor: int
    session_id: str = Field(json_schema_extra=_UUID)
    session_revision: int
    tick: int
    type: str
    target: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    command_id: str = Field(description="Echoes the client idempotency key.")
    sequence: int
    status: CommandStatus
    reason_code: ReasonCode | None = None
    session_revision: int
    current_tick: int
    events: list[EventEnvelope]
    state_summary: dict[str, Any]


class AdvanceRequest(BaseModel):
    ticks: StrictInt = Field(ge=0)
    expected_revision: StrictInt | None = None


class AdvanceResponse(BaseModel):
    session_revision: int
    current_tick: int
    events: list[EventEnvelope]
    state_summary: dict[str, Any]


class EventListResponse(BaseModel):
    session_id: str = Field(json_schema_extra=_UUID)
    events: list[EventEnvelope]


class HealthResponse(BaseModel):
    status: str


class ReadinessComponent(BaseModel):
    ok: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    components: dict[str, ReadinessComponent]
    supported_state_version: int

"""API request/response schemas.

`StrictInt` is used for `ticks`, `seed`, and `expected_revision` so that Python's
`bool` (a subtype of `int`) and string inputs are rejected at the API boundary
(SIM-FU-001).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, StrictInt


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class CreateSessionRequest(BaseModel):
    seed: StrictInt = 0
    users: StrictInt = Field(default=0, ge=0)


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str
    revision: int
    current_tick: int
    state_version: int
    created_at: str


class EconomySummary(BaseModel):
    cash: float | None = None
    revenue_total: float | None = None
    cost_total: float | None = None


class IncidentSummary(BaseModel):
    type: str | None = None
    target: str | None = None
    phase: str | None = None


class SessionSummaryResponse(BaseModel):
    session_id: str
    status: str
    revision: int
    current_tick: int
    speed: int
    paused: bool
    economy: EconomySummary
    user_trust: float | None = None
    investor_trust: float | None = None
    active_incidents: list[IncidentSummary]
    updated_at: str


class SnapshotResponse(BaseModel):
    session_id: str
    revision: int
    simulation_state_version: int
    snapshot: dict[str, Any]


class CommandRequest(BaseModel):
    command_id: str = Field(min_length=1)
    command_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_revision: StrictInt | None = None


class EventEnvelope(BaseModel):
    event_id: str
    cursor: int
    session_id: str
    session_revision: int
    tick: int
    type: str
    target: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    command_id: str
    sequence: int
    status: str
    reason_code: str | None = None
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
    session_id: str
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

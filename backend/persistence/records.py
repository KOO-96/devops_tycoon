"""Storage-agnostic domain records shared by all persistence backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"


class CommandStatus(StrEnum):
    APPLIED = "APPLIED"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    DUPLICATE_COMMAND_ID = "DUPLICATE_COMMAND_ID"
    COMMAND_OUT_OF_ORDER = "COMMAND_OUT_OF_ORDER"
    COMMAND_REJECTED = "COMMAND_REJECTED"


@dataclass
class SessionRecord:
    id: str
    status: SessionStatus
    simulation_state: dict[str, Any]
    simulation_state_version: int
    revision: int
    next_command_sequence: int
    created_at: datetime
    updated_at: datetime


@dataclass
class CommandRecord:
    id: str  # backend row id
    session_id: str
    command_id: str
    sequence: int
    command_type: str
    payload_hash: str
    status: CommandStatus
    result: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


@dataclass
class EventRecord:
    cursor: int  # monotonic per session (assigned by store)
    event_id: str  # backend-assigned UUID
    session_id: str
    session_revision: int
    tick: int
    event_type: str
    target: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

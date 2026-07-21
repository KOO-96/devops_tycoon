"""Incident types and their lifecycle state.

Lifecycle (master-plan / sim prompt §19):
    (no incident) -> WARNING -> ACTIVE -> RECOVERING -> RECOVERED -> (removed)

A single incident object per (type, target) key prevents the same failure from
being re-emitted every tick. After RECOVERED the incident is removed and a
cooldown blocks immediate re-arm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IncidentType(StrEnum):
    LB_IMBALANCE = "LB_IMBALANCE"
    APP_CPU_OVERLOAD = "APP_CPU_OVERLOAD"
    APP_MEM_SATURATION = "APP_MEM_SATURATION"
    DB_CONNECTION_POOL_EXHAUSTION = "DB_CONNECTION_POOL_EXHAUSTION"
    DB_CPU_SATURATION = "DB_CPU_SATURATION"
    CACHE_MISS_SPIKE = "CACHE_MISS_SPIKE"
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"
    NO_HEALTHY_SERVER = "NO_HEALTHY_SERVER"


class IncidentPhase(StrEnum):
    WARNING = "WARNING"
    ACTIVE = "ACTIVE"
    RECOVERING = "RECOVERING"
    RECOVERED = "RECOVERED"


# Related event id in the approved catalog, for CTO evidence traceability.
INCIDENT_EVENT_ID: dict[IncidentType, str] = {
    IncidentType.LB_IMBALANCE: "EVT-LB-001",
    IncidentType.APP_CPU_OVERLOAD: "EVT-APP-001",
    IncidentType.APP_MEM_SATURATION: "EVT-APP-002",
    IncidentType.DB_CONNECTION_POOL_EXHAUSTION: "EVT-DB-001",
    IncidentType.DB_CPU_SATURATION: "EVT-DB-002",
    IncidentType.CACHE_MISS_SPIKE: "EVT-CACHE-001",
    IncidentType.REQUEST_TIMEOUT: "EVT-DB-001",
    IncidentType.NO_HEALTHY_SERVER: "EVT-SRV-001",
}


def incident_key(incident_type: IncidentType, target: str) -> str:
    return f"{incident_type.value}:{target}"


@dataclass
class Incident:
    type: IncidentType
    target: str
    phase: IncidentPhase
    opened_tick: int
    updated_tick: int
    # First tick a warning sign was observable (for response-window accounting).
    warning_since_tick: int = 0
    metric: float = 0.0
    event_id: str = ""

    def key(self) -> str:
        return incident_key(self.type, self.target)

    def to_dict(self) -> dict[str, object]:
        return {
            "type": self.type.value,
            "target": self.target,
            "phase": self.phase.value,
            "opened_tick": self.opened_tick,
            "updated_tick": self.updated_tick,
            "warning_since_tick": self.warning_since_tick,
            "metric": self.metric,
            "event_id": self.event_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Incident:
        return cls(
            type=IncidentType(str(data["type"])),
            target=str(data["target"]),
            phase=IncidentPhase(str(data["phase"])),
            opened_tick=int(data["opened_tick"]),
            updated_tick=int(data["updated_tick"]),
            warning_since_tick=int(data.get("warning_since_tick", 0)),
            metric=float(data.get("metric", 0.0)),
            event_id=str(data.get("event_id", "")),
        )


@dataclass
class IncidentBook:
    """All active incidents plus per-key cooldown bookkeeping."""

    active: dict[str, Incident] = field(default_factory=dict)
    # key -> tick until which re-arming is blocked.
    cooldown_until: dict[str, int] = field(default_factory=dict)

    def get(self, key: str) -> Incident | None:
        return self.active.get(key)

    def to_dict(self) -> dict[str, object]:
        return {
            "active": {k: inc.to_dict() for k, inc in self.active.items()},
            "cooldown_until": dict(self.cooldown_until),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IncidentBook:
        active_raw = data.get("active") or {}
        cooldown_raw = data.get("cooldown_until") or {}
        return cls(
            active={k: Incident.from_dict(v) for k, v in active_raw.items()},
            cooldown_until={k: int(v) for k, v in cooldown_raw.items()},
        )

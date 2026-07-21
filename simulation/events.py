"""Domain events (one-off facts) and a bounded ring buffer.

Domain events are distinct from Incident *state* (see ``incidents``): events are
momentary facts (a request completed, a pool was exhausted this tick), while an
incident is a persistent condition with a lifecycle. Events are capped in a ring
buffer so long runs never accumulate unbounded memory (sim prompt §25).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DomainEventType(StrEnum):
    REQUEST_CREATED = "REQUEST_CREATED"
    REQUEST_ROUTED = "REQUEST_ROUTED"
    REQUEST_COMPLETED = "REQUEST_COMPLETED"
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"
    REQUEST_DROPPED = "REQUEST_DROPPED"
    REQUEST_FAILED = "REQUEST_FAILED"
    CACHE_HIT = "CACHE_HIT"
    CACHE_MISS = "CACHE_MISS"
    CACHE_WRITE = "CACHE_WRITE"
    CACHE_EVICTION = "CACHE_EVICTION"
    CONNECTION_ACQUIRED = "CONNECTION_ACQUIRED"
    CONNECTION_POOL_EXHAUSTED = "CONNECTION_POOL_EXHAUSTED"
    NODE_OVERLOADED = "NODE_OVERLOADED"
    NODE_RECOVERED = "NODE_RECOVERED"
    NODE_DOWN = "NODE_DOWN"
    INCIDENT_OPENED = "INCIDENT_OPENED"
    INCIDENT_PHASE_CHANGED = "INCIDENT_PHASE_CHANGED"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    COMMAND_APPLIED = "COMMAND_APPLIED"
    COMMAND_REJECTED = "COMMAND_REJECTED"


@dataclass
class DomainEvent:
    tick: int
    type: DomainEventType
    target: str = ""
    detail: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "tick": self.tick,
            "type": self.type.value,
            "target": self.target,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
        detail = data.get("detail") or {}
        return cls(
            tick=int(data["tick"]),
            type=DomainEventType(str(data["type"])),
            target=str(data.get("target", "")),
            detail=dict(detail),
        )


@dataclass
class EventLog:
    """A bounded FIFO of the most recent domain events.

    Long-term storage (``items``) is a ring buffer capped at ``max_size``. A
    transient per-step *capture sink* separately collects everything emitted
    during a step, so the caller never relies on list indices to detect new
    events even after old ones are trimmed (D1 fix).
    """

    max_size: int = 500
    items: list[DomainEvent] = field(default_factory=list)
    # Transient, not serialized: receives events emitted during the current step.
    _sink: list[DomainEvent] | None = field(default=None, repr=False, compare=False)

    def emit(self, event: DomainEvent) -> None:
        self.items.append(event)
        overflow = len(self.items) - self.max_size
        if overflow > 0:
            del self.items[:overflow]
        if self._sink is not None:
            self._sink.append(event)

    def begin_capture(self, sink: list[DomainEvent]) -> None:
        self._sink = sink

    def end_capture(self) -> None:
        self._sink = None

    def recent(self, count: int) -> list[DomainEvent]:
        if count <= 0:
            return []
        return list(self.items[-count:])

    def to_dict(self) -> dict[str, object]:
        return {"max_size": self.max_size, "items": [e.to_dict() for e in self.items]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventLog:
        items_raw = data.get("items") or []
        return cls(
            max_size=int(data.get("max_size", 500)),
            items=[DomainEvent.from_dict(d) for d in items_raw],
        )

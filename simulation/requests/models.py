"""Request model.

Traffic is simulated as aggregate per-tick counts for correctness and
performance (sim prompt §12, §25). A small bounded set of representative
``Request`` objects is kept for visualization/tracing; the bulk of traffic is
aggregated, never stored as unbounded per-request objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RequestState(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    CACHE_HIT = "CACHE_HIT"
    CACHE_MISS = "CACHE_MISS"
    DB_WAIT = "DB_WAIT"
    COMPLETED = "COMPLETED"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


@dataclass
class Request:
    """A representative (sampled) request for visualization/tracing."""

    id: str
    request_type: str
    created_tick: int
    location: str  # node id currently holding the request, or "users"
    cacheable: bool
    db_required: bool
    timeout_tick: int
    retry_count: int = 0
    max_retry: int = 2
    business_value: float = 0.01
    state: RequestState = RequestState.CREATED

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "request_type": self.request_type,
            "created_tick": self.created_tick,
            "location": self.location,
            "cacheable": self.cacheable,
            "db_required": self.db_required,
            "timeout_tick": self.timeout_tick,
            "retry_count": self.retry_count,
            "max_retry": self.max_retry,
            "business_value": self.business_value,
            "state": self.state.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Request:
        return cls(
            id=str(data["id"]),
            request_type=str(data["request_type"]),
            created_tick=int(data["created_tick"]),
            location=str(data["location"]),
            cacheable=bool(data["cacheable"]),
            db_required=bool(data["db_required"]),
            timeout_tick=int(data["timeout_tick"]),
            retry_count=int(data["retry_count"]),
            max_retry=int(data["max_retry"]),
            business_value=float(data["business_value"]),
            state=RequestState(str(data["state"])),
        )


@dataclass
class TickTraffic:
    """Aggregate traffic figures produced for a single tick."""

    generated: int = 0
    routed: int = 0
    dropped_no_server: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_evictions: int = 0
    db_queries: int = 0
    completed: int = 0
    timed_out: int = 0
    failed: int = 0
    retried: int = 0
    per_server_routed: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.per_server_routed is None:
            self.per_server_routed = {}

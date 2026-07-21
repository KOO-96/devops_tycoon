"""Redis cache node model.

Stale-cache groundwork (EVT-CACHE-003) is represented via ``cached_version`` /
``source_version`` / ``expire_tick`` fields so the model is ready without
committing to an invalidation policy that Event has not confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from simulation.nodes.base import Health, NodeKind


@dataclass
class RedisCache:
    id: str
    enabled: bool = True
    health: Health = Health.HEALTHY
    capacity_entries: int = 10000
    used_entries: int = 0
    ttl_ticks: int = 300
    # Observed hit rate for the most recent tick (0.0..1.0).
    hit_rate: float = 0.0
    # Stale-cache groundwork (not yet driven by an invalidation policy).
    cached_version: int = 0
    source_version: int = 0
    expire_tick: int = 0

    kind: NodeKind = NodeKind.REDIS

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "id": self.id,
            "enabled": self.enabled,
            "health": self.health.value,
            "capacity_entries": self.capacity_entries,
            "used_entries": self.used_entries,
            "ttl_ticks": self.ttl_ticks,
            "hit_rate": self.hit_rate,
            "cached_version": self.cached_version,
            "source_version": self.source_version,
            "expire_tick": self.expire_tick,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RedisCache:
        return cls(
            id=str(data["id"]),
            enabled=bool(data["enabled"]),
            health=Health(str(data["health"])),
            capacity_entries=int(data["capacity_entries"]),
            used_entries=int(data["used_entries"]),
            ttl_ticks=int(data["ttl_ticks"]),
            hit_rate=float(data["hit_rate"]),
            cached_version=int(data["cached_version"]),
            source_version=int(data["source_version"]),
            expire_tick=int(data["expire_tick"]),
        )

    def is_available(self) -> bool:
        return self.enabled and self.health != Health.DOWN

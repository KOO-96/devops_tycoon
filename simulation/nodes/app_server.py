"""App server node model and resource state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from simulation.nodes.base import Health, NodeKind


@dataclass
class AppServer:
    id: str
    enabled: bool = True
    health: Health = Health.HEALTHY
    version: str = "v1"
    weight: float = 1.0
    # Capacities are normalized to 1.0 == 100% utilization.
    cpu_usage: float = 0.0
    mem_usage: float = 0.0
    queue_length: int = 0
    queue_capacity: int = 100
    # Per-tick requests actually accepted (for observability / LB fairness).
    last_request_rate: float = 0.0
    # Memory leak per tick (EVT-APP-002 groundwork; 0.0 = no leak).
    mem_leak_per_tick: float = 0.0
    # Persistent, monotonic leak component (reset by deploy/restart).
    mem_leak_accum: float = 0.0

    kind: NodeKind = NodeKind.APP_SERVER

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "id": self.id,
            "enabled": self.enabled,
            "health": self.health.value,
            "version": self.version,
            "weight": self.weight,
            "cpu_usage": self.cpu_usage,
            "mem_usage": self.mem_usage,
            "queue_length": self.queue_length,
            "queue_capacity": self.queue_capacity,
            "last_request_rate": self.last_request_rate,
            "mem_leak_per_tick": self.mem_leak_per_tick,
            "mem_leak_accum": self.mem_leak_accum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppServer:
        return cls(
            id=str(data["id"]),
            enabled=bool(data["enabled"]),
            health=Health(str(data["health"])),
            version=str(data["version"]),
            weight=float(data["weight"]),
            cpu_usage=float(data["cpu_usage"]),
            mem_usage=float(data["mem_usage"]),
            queue_length=int(data["queue_length"]),
            queue_capacity=int(data["queue_capacity"]),
            last_request_rate=float(data["last_request_rate"]),
            mem_leak_per_tick=float(data["mem_leak_per_tick"]),
            mem_leak_accum=float(data.get("mem_leak_accum", 0.0)),
        )

    def is_available(self) -> bool:
        """A server receives traffic only if enabled and not Down."""
        return self.enabled and self.health != Health.DOWN

"""PostgreSQL node model with a single connection pool (MVP simplification).

master-plan leaves per-service vs single pool open; the MVP uses one pool
(documented in simulation-state-model.md). Fields cover EVT-DB-001 (pool
exhaustion) and EVT-DB-002 (DB CPU saturation / slow query groundwork).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from simulation.nodes.base import Health, NodeKind


@dataclass
class Postgres:
    id: str
    enabled: bool = True
    health: Health = Health.HEALTHY
    cpu_usage: float = 0.0
    max_connections: int = 100
    active_connections: int = 0
    waiting_connections: int = 0
    query_queue: int = 0

    kind: NodeKind = NodeKind.POSTGRESQL

    def to_dict(self) -> Dict[str, object]:
        return {
            "kind": self.kind.value,
            "id": self.id,
            "enabled": self.enabled,
            "health": self.health.value,
            "cpu_usage": self.cpu_usage,
            "max_connections": self.max_connections,
            "active_connections": self.active_connections,
            "waiting_connections": self.waiting_connections,
            "query_queue": self.query_queue,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Postgres":
        return cls(
            id=str(data["id"]),
            enabled=bool(data["enabled"]),
            health=Health(str(data["health"])),
            cpu_usage=float(data["cpu_usage"]),  # type: ignore[arg-type]
            max_connections=int(data["max_connections"]),  # type: ignore[arg-type]
            active_connections=int(data["active_connections"]),  # type: ignore[arg-type]
            waiting_connections=int(data["waiting_connections"]),  # type: ignore[arg-type]
            query_queue=int(data["query_queue"]),  # type: ignore[arg-type]
        )

    def connection_ratio(self) -> float:
        if self.max_connections <= 0:
            return 0.0
        return self.active_connections / self.max_connections

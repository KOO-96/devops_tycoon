"""Load balancer node model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from simulation.nodes.base import LBAlgorithm, NodeKind


@dataclass
class LoadBalancer:
    id: str
    enabled: bool = True
    algorithm: LBAlgorithm = LBAlgorithm.ROUND_ROBIN
    sticky: bool = False
    # Round-robin cursor, persisted so distribution is deterministic across ticks
    # and across save/restore.
    rr_cursor: int = 0

    kind: NodeKind = NodeKind.LOAD_BALANCER

    def to_dict(self) -> Dict[str, object]:
        return {
            "kind": self.kind.value,
            "id": self.id,
            "enabled": self.enabled,
            "algorithm": self.algorithm.value,
            "sticky": self.sticky,
            "rr_cursor": self.rr_cursor,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "LoadBalancer":
        return cls(
            id=str(data["id"]),
            enabled=bool(data["enabled"]),
            algorithm=LBAlgorithm(str(data["algorithm"])),
            sticky=bool(data["sticky"]),
            rr_cursor=int(data["rr_cursor"]),  # type: ignore[arg-type]
        )

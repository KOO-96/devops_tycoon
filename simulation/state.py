"""GameState: the complete, serializable, deterministic simulation state.

Everything needed to resume a run lives here, including the RNG state and clock,
so that ``serialize -> deserialize -> continue`` yields identical results
(master-plan 4.11, sim prompt §9).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from simulation.clock import Clock
from simulation.events import EventLog
from simulation.incidents.models import IncidentBook
from simulation.nodes.app_server import AppServer
from simulation.nodes.load_balancer import LoadBalancer
from simulation.nodes.postgresql import Postgres
from simulation.nodes.redis import RedisCache
from simulation.requests.models import Request
from simulation.rng import Rng

STATE_VERSION = 1


@dataclass
class Economy:
    cash: float = 1000.0
    revenue_total: float = 0.0
    cost_total: float = 0.0
    revenue_last_tick: float = 0.0
    cost_last_tick: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "cash": self.cash,
            "revenue_total": self.revenue_total,
            "cost_total": self.cost_total,
            "revenue_last_tick": self.revenue_last_tick,
            "cost_last_tick": self.cost_last_tick,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Economy":
        return cls(
            cash=float(data["cash"]),  # type: ignore[arg-type]
            revenue_total=float(data["revenue_total"]),  # type: ignore[arg-type]
            cost_total=float(data["cost_total"]),  # type: ignore[arg-type]
            revenue_last_tick=float(data["revenue_last_tick"]),  # type: ignore[arg-type]
            cost_last_tick=float(data["cost_last_tick"]),  # type: ignore[arg-type]
        )


@dataclass
class GameState:
    simulation_id: str
    clock: Clock
    rng: Rng
    version: int = STATE_VERSION
    users: int = 0
    load_balancers: Dict[str, LoadBalancer] = field(default_factory=dict)
    app_servers: Dict[str, AppServer] = field(default_factory=dict)
    caches: Dict[str, RedisCache] = field(default_factory=dict)
    databases: Dict[str, Postgres] = field(default_factory=dict)
    connections: List[Tuple[str, str]] = field(default_factory=list)
    incidents: IncidentBook = field(default_factory=IncidentBook)
    events: EventLog = field(default_factory=EventLog)
    applied_command_ids: List[str] = field(default_factory=list)
    economy: Economy = field(default_factory=Economy)
    user_trust: float = 100.0
    investor_trust: float = 100.0
    tech_debt: float = 0.0
    ops_complexity: float = 0.0
    next_request_id: int = 1
    pending_retries: int = 0
    sample_requests: List[Request] = field(default_factory=list)
    sample_capacity: int = 50

    # -- connection graph helpers ------------------------------------------

    def targets_of(self, src_id: str) -> List[str]:
        return [dst for (s, dst) in self.connections if s == src_id]

    def app_servers_behind(self, lb_id: str) -> List[AppServer]:
        ids = self.targets_of(lb_id)
        return [self.app_servers[i] for i in ids if i in self.app_servers]

    def cache_for(self, app_id: str) -> Optional[RedisCache]:
        for dst in self.targets_of(app_id):
            if dst in self.caches:
                return self.caches[dst]
        return None

    def database_for(self, app_id: str) -> Optional[Postgres]:
        for dst in self.targets_of(app_id):
            if dst in self.databases:
                return self.databases[dst]
        return None

    def node_exists(self, node_id: str) -> bool:
        return (
            node_id in self.app_servers
            or node_id in self.load_balancers
            or node_id in self.caches
            or node_id in self.databases
        )

    # -- serialization ------------------------------------------------------

    def to_dict(self) -> Dict[str, object]:
        return {
            "version": self.version,
            "simulation_id": self.simulation_id,
            "clock": {
                "tick": self.clock.tick,
                "tick_ms": self.clock.tick_ms,
                "speed": self.clock.speed,
                "paused": self.clock.paused,
            },
            "rng_state": self.rng.to_state(),
            "users": self.users,
            "load_balancers": {k: n.to_dict() for k, n in self.load_balancers.items()},
            "app_servers": {k: n.to_dict() for k, n in self.app_servers.items()},
            "caches": {k: n.to_dict() for k, n in self.caches.items()},
            "databases": {k: n.to_dict() for k, n in self.databases.items()},
            "connections": [list(edge) for edge in self.connections],
            "incidents": self.incidents.to_dict(),
            "events": self.events.to_dict(),
            "applied_command_ids": list(self.applied_command_ids),
            "economy": self.economy.to_dict(),
            "user_trust": self.user_trust,
            "investor_trust": self.investor_trust,
            "tech_debt": self.tech_debt,
            "ops_complexity": self.ops_complexity,
            "next_request_id": self.next_request_id,
            "pending_retries": self.pending_retries,
            "sample_requests": [r.to_dict() for r in self.sample_requests],
            "sample_capacity": self.sample_capacity,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "GameState":
        clock_raw = data["clock"]
        clock = Clock(
            tick=int(clock_raw["tick"]),  # type: ignore[index,arg-type]
            tick_ms=int(clock_raw["tick_ms"]),  # type: ignore[index,arg-type]
            speed=int(clock_raw["speed"]),  # type: ignore[index,arg-type]
            paused=bool(clock_raw["paused"]),  # type: ignore[index]
        )
        connections_raw = data.get("connections") or []
        return cls(
            simulation_id=str(data["simulation_id"]),
            clock=clock,
            rng=Rng.from_state(int(data["rng_state"])),  # type: ignore[arg-type]
            version=int(data.get("version", STATE_VERSION)),  # type: ignore[arg-type]
            users=int(data["users"]),  # type: ignore[arg-type]
            load_balancers={
                k: LoadBalancer.from_dict(v) for k, v in (data["load_balancers"]).items()  # type: ignore[union-attr]
            },
            app_servers={
                k: AppServer.from_dict(v) for k, v in (data["app_servers"]).items()  # type: ignore[union-attr]
            },
            caches={k: RedisCache.from_dict(v) for k, v in (data["caches"]).items()},  # type: ignore[union-attr]
            databases={k: Postgres.from_dict(v) for k, v in (data["databases"]).items()},  # type: ignore[union-attr]
            connections=[(str(e[0]), str(e[1])) for e in connections_raw],  # type: ignore[index]
            incidents=IncidentBook.from_dict(data["incidents"]),  # type: ignore[arg-type]
            events=EventLog.from_dict(data["events"]),  # type: ignore[arg-type]
            applied_command_ids=[str(c) for c in (data.get("applied_command_ids") or [])],  # type: ignore[union-attr]
            economy=Economy.from_dict(data["economy"]),  # type: ignore[arg-type]
            user_trust=float(data["user_trust"]),  # type: ignore[arg-type]
            investor_trust=float(data["investor_trust"]),  # type: ignore[arg-type]
            tech_debt=float(data["tech_debt"]),  # type: ignore[arg-type]
            ops_complexity=float(data["ops_complexity"]),  # type: ignore[arg-type]
            next_request_id=int(data["next_request_id"]),  # type: ignore[arg-type]
            pending_retries=int(data.get("pending_retries", 0)),  # type: ignore[arg-type]
            sample_requests=[Request.from_dict(r) for r in (data.get("sample_requests") or [])],  # type: ignore[union-attr]
            sample_capacity=int(data.get("sample_capacity", 50)),  # type: ignore[arg-type]
        )

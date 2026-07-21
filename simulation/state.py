"""GameState: the complete, serializable, deterministic simulation state.

Everything needed to resume a run lives here, including the RNG state and clock,
so that ``serialize -> deserialize -> continue`` yields identical results
(master-plan 4.11, sim prompt §9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulation.clock import Clock
from simulation.errors import UnsupportedStateVersionError
from simulation.events import EventLog
from simulation.incidents.models import IncidentBook
from simulation.nodes.app_server import AppServer
from simulation.nodes.load_balancer import LoadBalancer
from simulation.nodes.postgresql import Postgres
from simulation.nodes.redis import RedisCache
from simulation.requests.models import Request
from simulation.rng import Rng

# v2: replaced the unbounded command ledger with a sequence watermark + bounded
# recent-id window (D5). Older snapshots are rejected for migration.
STATE_VERSION = 2


@dataclass
class Economy:
    cash: float = 1000.0
    revenue_total: float = 0.0
    cost_total: float = 0.0
    revenue_last_tick: float = 0.0
    cost_last_tick: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cash": self.cash,
            "revenue_total": self.revenue_total,
            "cost_total": self.cost_total,
            "revenue_last_tick": self.revenue_last_tick,
            "cost_last_tick": self.cost_last_tick,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Economy:
        return cls(
            cash=float(data["cash"]),
            revenue_total=float(data["revenue_total"]),
            cost_total=float(data["cost_total"]),
            revenue_last_tick=float(data["revenue_last_tick"]),
            cost_last_tick=float(data["cost_last_tick"]),
        )


@dataclass
class GameState:
    simulation_id: str
    clock: Clock
    rng: Rng
    version: int = STATE_VERSION
    users: int = 0
    load_balancers: dict[str, LoadBalancer] = field(default_factory=dict)
    app_servers: dict[str, AppServer] = field(default_factory=dict)
    caches: dict[str, RedisCache] = field(default_factory=dict)
    databases: dict[str, Postgres] = field(default_factory=dict)
    connections: list[tuple[str, str]] = field(default_factory=list)
    incidents: IncidentBook = field(default_factory=IncidentBook)
    events: EventLog = field(default_factory=EventLog)
    # Idempotency (D5): bounded recent-id window + monotonic watermark.
    recent_command_ids: list[str] = field(default_factory=list)
    last_applied_command_sequence: int = 0
    economy: Economy = field(default_factory=Economy)
    user_trust: float = 100.0
    investor_trust: float = 100.0
    tech_debt: float = 0.0
    ops_complexity: float = 0.0
    next_request_id: int = 1
    pending_retries: int = 0
    sample_requests: list[Request] = field(default_factory=list)
    sample_capacity: int = 50

    # -- connection graph helpers ------------------------------------------

    def targets_of(self, src_id: str) -> list[str]:
        return [dst for (s, dst) in self.connections if s == src_id]

    def app_servers_behind(self, lb_id: str) -> list[AppServer]:
        ids = self.targets_of(lb_id)
        return [self.app_servers[i] for i in ids if i in self.app_servers]

    def cache_for(self, app_id: str) -> RedisCache | None:
        for dst in self.targets_of(app_id):
            if dst in self.caches:
                return self.caches[dst]
        return None

    def database_for(self, app_id: str) -> Postgres | None:
        for dst in self.targets_of(app_id):
            if dst in self.databases:
                return self.databases[dst]
        return None

    def resolve_data_path(self, app_id: str) -> tuple[RedisCache | None, Postgres | None]:
        """Resolve the (cache, database) an app server actually reaches.

        Rules (D2): app's directly connected cache first; then that cache's
        downstream DB (App -> Redis -> PostgreSQL); otherwise the app's directly
        connected DB; otherwise no DB. A visited set guards against cycles.
        """
        visited: set[str] = {app_id}
        cache = self.cache_for(app_id)
        db: Postgres | None = None
        if cache is not None and cache.id not in visited:
            visited.add(cache.id)
            for dst in self.targets_of(cache.id):
                if dst in self.databases and dst not in visited:
                    db = self.databases[dst]
                    break
        if db is None:
            db = self.database_for(app_id)
        return cache, db

    def node_exists(self, node_id: str) -> bool:
        return (
            node_id in self.app_servers
            or node_id in self.load_balancers
            or node_id in self.caches
            or node_id in self.databases
        )

    # -- serialization ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
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
            "recent_command_ids": list(self.recent_command_ids),
            "last_applied_command_sequence": self.last_applied_command_sequence,
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
    def from_dict(cls, data: dict[str, Any]) -> GameState:
        received = int(data.get("version", 0))
        if received != STATE_VERSION:
            raise UnsupportedStateVersionError(expected=STATE_VERSION, received=received)

        clock_raw = data["clock"]
        clock = Clock(
            tick=int(clock_raw["tick"]),
            tick_ms=int(clock_raw["tick_ms"]),
            speed=int(clock_raw["speed"]),
            paused=bool(clock_raw["paused"]),
        )
        return cls(
            simulation_id=str(data["simulation_id"]),
            clock=clock,
            rng=Rng.from_state(int(data["rng_state"])),
            version=received,
            users=int(data["users"]),
            load_balancers={
                k: LoadBalancer.from_dict(v) for k, v in data["load_balancers"].items()
            },
            app_servers={k: AppServer.from_dict(v) for k, v in data["app_servers"].items()},
            caches={k: RedisCache.from_dict(v) for k, v in data["caches"].items()},
            databases={k: Postgres.from_dict(v) for k, v in data["databases"].items()},
            connections=[(str(e[0]), str(e[1])) for e in (data.get("connections") or [])],
            incidents=IncidentBook.from_dict(data["incidents"]),
            events=EventLog.from_dict(data["events"]),
            recent_command_ids=[str(c) for c in (data.get("recent_command_ids") or [])],
            last_applied_command_sequence=int(data.get("last_applied_command_sequence", 0)),
            economy=Economy.from_dict(data["economy"]),
            user_trust=float(data["user_trust"]),
            investor_trust=float(data["investor_trust"]),
            tech_debt=float(data["tech_debt"]),
            ops_complexity=float(data["ops_complexity"]),
            next_request_id=int(data["next_request_id"]),
            pending_retries=int(data.get("pending_retries", 0)),
            sample_requests=[Request.from_dict(r) for r in (data.get("sample_requests") or [])],
            sample_capacity=int(data.get("sample_capacity", 50)),
        )

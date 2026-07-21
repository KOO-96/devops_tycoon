"""Observable metric snapshot produced each tick.

This is the observability surface Backend forwards and Frontend renders, and the
factual basis for CTO evidence. It contains only *observable* facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from simulation.requests.models import TickTraffic
from simulation.state import GameState


@dataclass
class MetricSnapshot:
    tick: int
    users: int
    traffic: Dict[str, int] = field(default_factory=dict)
    app_servers: Dict[str, Dict[str, object]] = field(default_factory=dict)
    databases: Dict[str, Dict[str, object]] = field(default_factory=dict)
    caches: Dict[str, Dict[str, object]] = field(default_factory=dict)
    active_incidents: List[Dict[str, object]] = field(default_factory=list)
    cash: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "tick": self.tick,
            "users": self.users,
            "traffic": self.traffic,
            "app_servers": self.app_servers,
            "databases": self.databases,
            "caches": self.caches,
            "active_incidents": self.active_incidents,
            "cash": self.cash,
        }


def build_snapshot(state: GameState, traffic: TickTraffic) -> MetricSnapshot:
    snap = MetricSnapshot(tick=state.clock.tick, users=state.users, cash=state.economy.cash)
    snap.traffic = {
        "generated": traffic.generated,
        "routed": traffic.routed,
        "dropped_no_server": traffic.dropped_no_server,
        "cache_hits": traffic.cache_hits,
        "cache_misses": traffic.cache_misses,
        "db_queries": traffic.db_queries,
        "completed": traffic.completed,
        "timed_out": traffic.timed_out,
        "retried": traffic.retried,
    }
    for sid, server in state.app_servers.items():
        snap.app_servers[sid] = {
            "cpu_usage": server.cpu_usage,
            "mem_usage": server.mem_usage,
            "queue_length": server.queue_length,
            "health": server.health.value,
            "enabled": server.enabled,
            "version": server.version,
            "request_rate": server.last_request_rate,
        }
    for did, db in state.databases.items():
        snap.databases[did] = {
            "connection_ratio": db.connection_ratio(),
            "active_connections": db.active_connections,
            "waiting_connections": db.waiting_connections,
            "cpu_usage": db.cpu_usage,
            "health": db.health.value,
        }
    for cid, cache in state.caches.items():
        snap.caches[cid] = {
            "hit_rate": cache.hit_rate,
            "used_entries": cache.used_entries,
            "capacity_entries": cache.capacity_entries,
            "enabled": cache.enabled,
        }
    snap.active_incidents = [inc.to_dict() for inc in state.incidents.active.values()]
    return snap

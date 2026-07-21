"""Player commands and their (idempotent) application to GameState.

A command is applied at most once: its ``id`` is recorded in
``state.applied_command_ids`` and a duplicate id is rejected without mutating
game state (sim prompt §11). Commands only *configure* the game board; the
per-tick facts are computed by the engine, not by commands.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

from simulation.events import DomainEvent, DomainEventType
from simulation.nodes.app_server import AppServer
from simulation.nodes.base import LBAlgorithm
from simulation.nodes.load_balancer import LoadBalancer
from simulation.nodes.postgresql import Postgres
from simulation.nodes.redis import RedisCache
from simulation.state import GameState

# Allowed directed connections (src_kind_dict, dst_kind_dict) enforced by CONNECT.
_ALLOWED_EDGES = {
    ("load_balancers", "app_servers"),
    ("app_servers", "caches"),
    ("app_servers", "databases"),
}


class CommandType(str, Enum):
    ADD_NODE = "ADD_NODE"
    REMOVE_NODE = "REMOVE_NODE"
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"
    SET_LB_CONFIG = "SET_LB_CONFIG"
    ENABLE_SERVER = "ENABLE_SERVER"
    DISABLE_SERVER = "DISABLE_SERVER"
    SET_REDIS_CONFIG = "SET_REDIS_CONFIG"
    SET_DB_POOL = "SET_DB_POOL"
    DEPLOY = "DEPLOY"
    ROLLBACK = "ROLLBACK"
    DISABLE_FEATURE = "DISABLE_FEATURE"
    PAUSE = "PAUSE"
    SET_SPEED = "SET_SPEED"


@dataclass
class Command:
    id: str
    type: CommandType
    target: str = ""
    payload: Dict[str, object] = None  # type: ignore[assignment]
    request_tick: int = 0

    def __post_init__(self) -> None:
        if self.payload is None:
            self.payload = {}


def _collection_of(state: GameState, node_id: str) -> str:
    if node_id in state.load_balancers:
        return "load_balancers"
    if node_id in state.app_servers:
        return "app_servers"
    if node_id in state.caches:
        return "caches"
    if node_id in state.databases:
        return "databases"
    return ""


def _reject(state: GameState, command: Command, reason: str) -> None:
    state.events.emit(
        DomainEvent(
            tick=state.clock.tick,
            type=DomainEventType.COMMAND_REJECTED,
            target=command.target,
            detail={"command_id": command.id, "type": command.type.value, "reason": reason},
        )
    )


def _accept(state: GameState, command: Command) -> None:
    state.events.emit(
        DomainEvent(
            tick=state.clock.tick,
            type=DomainEventType.COMMAND_APPLIED,
            target=command.target,
            detail={"command_id": command.id, "type": command.type.value},
        )
    )


def apply_commands(state: GameState, commands: List[Command]) -> None:
    """Apply commands in order, enforcing idempotency and validation."""
    applied = set(state.applied_command_ids)
    for command in commands:
        if command.id in applied:
            _reject(state, command, "duplicate_command_id")
            continue
        ok = _dispatch(state, command)
        # An id is consumed whether it succeeded or was validly rejected, so a
        # retried duplicate never re-applies.
        applied.add(command.id)
        state.applied_command_ids.append(command.id)
        if ok:
            _accept(state, command)


def _dispatch(state: GameState, command: Command) -> bool:  # noqa: C901 - explicit dispatch
    handler = _HANDLERS.get(command.type)
    if handler is None:
        _reject(state, command, "unknown_command_type")
        return False
    return handler(state, command)


def _add_node(state: GameState, command: Command) -> bool:
    node_id = command.target
    if not node_id or state.node_exists(node_id):
        _reject(state, command, "invalid_or_duplicate_node_id")
        return False
    kind = str(command.payload.get("node_kind", ""))
    if kind == "app_server":
        state.app_servers[node_id] = AppServer(
            id=node_id,
            weight=float(command.payload.get("weight", 1.0)),  # type: ignore[arg-type]
            queue_capacity=int(command.payload.get("queue_capacity", 100)),  # type: ignore[arg-type]
            mem_leak_per_tick=float(command.payload.get("mem_leak_per_tick", 0.0)),  # type: ignore[arg-type]
        )
    elif kind == "load_balancer":
        state.load_balancers[node_id] = LoadBalancer(id=node_id)
    elif kind == "redis":
        state.caches[node_id] = RedisCache(id=node_id)
    elif kind == "postgresql":
        state.databases[node_id] = Postgres(
            id=node_id,
            max_connections=int(command.payload.get("max_connections", 100)),  # type: ignore[arg-type]
        )
    else:
        _reject(state, command, "unknown_node_kind")
        return False
    return True


def _remove_node(state: GameState, command: Command) -> bool:
    coll = _collection_of(state, command.target)
    if not coll:
        _reject(state, command, "node_not_found")
        return False
    getattr(state, coll).pop(command.target, None)
    state.connections = [
        edge for edge in state.connections if command.target not in edge
    ]
    return True


def _connect(state: GameState, command: Command) -> bool:
    src = command.target
    dst = str(command.payload.get("to", ""))
    if not state.node_exists(src) or not state.node_exists(dst):
        _reject(state, command, "missing_node")
        return False
    pair = (_collection_of(state, src), _collection_of(state, dst))
    if pair not in _ALLOWED_EDGES:
        _reject(state, command, "connection_not_allowed")
        return False
    if (src, dst) in state.connections:
        _reject(state, command, "already_connected")
        return False
    state.connections.append((src, dst))
    return True


def _disconnect(state: GameState, command: Command) -> bool:
    src = command.target
    dst = str(command.payload.get("to", ""))
    if (src, dst) not in state.connections:
        _reject(state, command, "not_connected")
        return False
    state.connections.remove((src, dst))
    return True


def _set_lb_config(state: GameState, command: Command) -> bool:
    lb = state.load_balancers.get(command.target)
    if lb is None:
        _reject(state, command, "lb_not_found")
        return False
    if "algorithm" in command.payload:
        try:
            lb.algorithm = LBAlgorithm(str(command.payload["algorithm"]))
        except ValueError:
            _reject(state, command, "invalid_algorithm")
            return False
    if "sticky" in command.payload:
        lb.sticky = bool(command.payload["sticky"])
    return True


def _set_server_enabled(enabled: bool):  # type: ignore[no-untyped-def]
    def handler(state: GameState, command: Command) -> bool:
        server = state.app_servers.get(command.target)
        if server is None:
            _reject(state, command, "server_not_found")
            return False
        server.enabled = enabled
        return True

    return handler


def _set_redis_config(state: GameState, command: Command) -> bool:
    cache = state.caches.get(command.target)
    if cache is None:
        _reject(state, command, "cache_not_found")
        return False
    if "ttl_ticks" in command.payload:
        cache.ttl_ticks = max(0, int(command.payload["ttl_ticks"]))  # type: ignore[arg-type]
    if "capacity_entries" in command.payload:
        cache.capacity_entries = max(1, int(command.payload["capacity_entries"]))  # type: ignore[arg-type]
    if "enabled" in command.payload:
        cache.enabled = bool(command.payload["enabled"])
    return True


def _set_db_pool(state: GameState, command: Command) -> bool:
    db = state.databases.get(command.target)
    if db is None:
        _reject(state, command, "db_not_found")
        return False
    if "max_connections" in command.payload:
        db.max_connections = max(1, int(command.payload["max_connections"]))  # type: ignore[arg-type]
    return True


def _deploy(state: GameState, command: Command) -> bool:
    server = state.app_servers.get(command.target)
    if server is None:
        _reject(state, command, "server_not_found")
        return False
    new_version = str(command.payload.get("version", server.version))
    server.version = new_version
    # A fresh deploy resets accumulated leak; the payload may also set/clear the
    # per-tick leak rate (e.g. shipping a leak fix). EVT-APP-002.
    server.mem_leak_accum = 0.0
    if "mem_leak_per_tick" in command.payload:
        server.mem_leak_per_tick = float(command.payload["mem_leak_per_tick"])  # type: ignore[arg-type]
    return True


def _rollback(state: GameState, command: Command) -> bool:
    server = state.app_servers.get(command.target)
    if server is None:
        _reject(state, command, "server_not_found")
        return False
    prev = str(command.payload.get("to_version", ""))
    if not prev:
        _reject(state, command, "missing_target_version")
        return False
    server.version = prev
    return True


def _disable_feature(state: GameState, command: Command) -> bool:
    # MVP: feature flags are modeled only as an ops-complexity relief hook.
    return True


def _pause(state: GameState, command: Command) -> bool:
    state.clock.set_paused(bool(command.payload.get("paused", True)))
    return True


def _set_speed(state: GameState, command: Command) -> bool:
    speed = int(command.payload.get("speed", 1))  # type: ignore[arg-type]
    try:
        state.clock.set_speed(speed)
    except ValueError:
        _reject(state, command, "invalid_speed")
        return False
    return True


_HANDLERS = {
    CommandType.ADD_NODE: _add_node,
    CommandType.REMOVE_NODE: _remove_node,
    CommandType.CONNECT: _connect,
    CommandType.DISCONNECT: _disconnect,
    CommandType.SET_LB_CONFIG: _set_lb_config,
    CommandType.ENABLE_SERVER: _set_server_enabled(True),
    CommandType.DISABLE_SERVER: _set_server_enabled(False),
    CommandType.SET_REDIS_CONFIG: _set_redis_config,
    CommandType.SET_DB_POOL: _set_db_pool,
    CommandType.DEPLOY: _deploy,
    CommandType.ROLLBACK: _rollback,
    CommandType.DISABLE_FEATURE: _disable_feature,
    CommandType.PAUSE: _pause,
    CommandType.SET_SPEED: _set_speed,
}

"""Player commands and their (idempotent) application to GameState.

Idempotency (D5, DevCTO decision):
- Backend owns *permanent* idempotency and assigns a monotonic
  ``sequence`` per session command.
- Simulation keeps a **sequence watermark** (`last_applied_command_sequence`)
  plus a **bounded recent-id ledger** (`recent_command_ids`, size from
  BalanceConfig). The watermark blocks re-application even after an id ages out
  of the ledger.

Sequence policy (for `sequence >= 0`):
- `sequence < expected` -> already applied (rejected, no re-apply)
- `sequence > expected` -> out of order (rejected, sequence NOT consumed)
- `sequence == expected` -> applied; sequence consumed whether the handler
  succeeds or is validly rejected (only undeserializable commands are stopped
  earlier, by Backend).

Commands with `sequence < 0` (unsequenced) fall back to best-effort id dedup
within the recent window.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from simulation.config.models import BalanceConfig
from simulation.events import DomainEvent, DomainEventType
from simulation.nodes.app_server import AppServer
from simulation.nodes.base import LBAlgorithm
from simulation.nodes.load_balancer import LoadBalancer
from simulation.nodes.postgresql import Postgres
from simulation.nodes.redis import RedisCache
from simulation.state import GameState

# Allowed directed connections enforced by CONNECT.
_ALLOWED_EDGES = {
    ("load_balancers", "app_servers"),
    ("app_servers", "caches"),
    ("app_servers", "databases"),
    ("caches", "databases"),  # App -> Redis -> PostgreSQL
}


class CommandType(StrEnum):
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
    payload: dict[str, object] = field(default_factory=dict)
    request_tick: int = 0
    # Monotonic sequence assigned by Backend; -1 means unsequenced.
    sequence: int = -1


# --- typed payload accessors (keep mypy strict happy at the object boundary) --


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _as_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _as_str(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _as_bool(value: object, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


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


def apply_commands(state: GameState, commands: list[Command], config: BalanceConfig) -> None:
    """Apply commands in order with sequence-watermark + bounded-ledger idempotency."""
    ledger_size = max(1, config.get_int("command_ledger_size"))
    recent = set(state.recent_command_ids)
    for command in commands:
        consumed = _process_one(state, command, recent)
        if consumed:
            _record_id(state, command.id, ledger_size, recent)


def _process_one(state: GameState, command: Command, recent: set[str]) -> bool:
    """Return True if the command id should be recorded in the ledger."""
    if command.id in recent:
        _reject(state, command, "duplicate_command_id")
        return False

    if command.sequence >= 0:
        expected = state.last_applied_command_sequence + 1
        if command.sequence < expected:
            _reject(state, command, "already_applied")
            return False
        if command.sequence > expected:
            _reject(state, command, "command_out_of_order")
            return False  # do NOT consume: may arrive in order later
        ok = _dispatch(state, command)
        state.last_applied_command_sequence = command.sequence
        if ok:
            _accept(state, command)
        return True

    # Unsequenced: best-effort id dedup only.
    ok = _dispatch(state, command)
    if ok:
        _accept(state, command)
    return True


def _record_id(state: GameState, command_id: str, ledger_size: int, recent: set[str]) -> None:
    state.recent_command_ids.append(command_id)
    recent.add(command_id)
    while len(state.recent_command_ids) > ledger_size:
        oldest = state.recent_command_ids.pop(0)
        recent.discard(oldest)


def _dispatch(state: GameState, command: Command) -> bool:
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
    kind = _as_str(command.payload.get("node_kind"))
    if kind == "app_server":
        state.app_servers[node_id] = AppServer(
            id=node_id,
            weight=_as_float(command.payload.get("weight"), 1.0),
            queue_capacity=_as_int(command.payload.get("queue_capacity"), 100),
            mem_leak_per_tick=_as_float(command.payload.get("mem_leak_per_tick"), 0.0),
        )
    elif kind == "load_balancer":
        state.load_balancers[node_id] = LoadBalancer(id=node_id)
    elif kind == "redis":
        state.caches[node_id] = RedisCache(id=node_id)
    elif kind == "postgresql":
        state.databases[node_id] = Postgres(
            id=node_id,
            max_connections=_as_int(command.payload.get("max_connections"), 100),
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
    state.connections = [edge for edge in state.connections if command.target not in edge]
    return True


def _connect(state: GameState, command: Command) -> bool:
    src = command.target
    dst = _as_str(command.payload.get("to"))
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
    dst = _as_str(command.payload.get("to"))
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
            lb.algorithm = LBAlgorithm(_as_str(command.payload["algorithm"]))
        except ValueError:
            _reject(state, command, "invalid_algorithm")
            return False
    if "sticky" in command.payload:
        lb.sticky = _as_bool(command.payload["sticky"])
    return True


def _make_set_server_enabled(enabled: bool) -> Callable[[GameState, Command], bool]:
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
        cache.ttl_ticks = max(0, _as_int(command.payload["ttl_ticks"], cache.ttl_ticks))
    if "capacity_entries" in command.payload:
        cache.capacity_entries = max(
            1, _as_int(command.payload["capacity_entries"], cache.capacity_entries)
        )
    if "enabled" in command.payload:
        cache.enabled = _as_bool(command.payload["enabled"], cache.enabled)
    return True


def _set_db_pool(state: GameState, command: Command) -> bool:
    db = state.databases.get(command.target)
    if db is None:
        _reject(state, command, "db_not_found")
        return False
    if "max_connections" in command.payload:
        db.max_connections = max(1, _as_int(command.payload["max_connections"], db.max_connections))
    return True


def _deploy(state: GameState, command: Command) -> bool:
    server = state.app_servers.get(command.target)
    if server is None:
        _reject(state, command, "server_not_found")
        return False
    server.version = _as_str(command.payload.get("version"), server.version)
    # A fresh deploy resets accumulated leak; the payload may also set/clear the
    # per-tick leak rate (e.g. shipping a leak fix). EVT-APP-002.
    server.mem_leak_accum = 0.0
    if "mem_leak_per_tick" in command.payload:
        server.mem_leak_per_tick = _as_float(
            command.payload["mem_leak_per_tick"], server.mem_leak_per_tick
        )
    return True


def _rollback(state: GameState, command: Command) -> bool:
    server = state.app_servers.get(command.target)
    if server is None:
        _reject(state, command, "server_not_found")
        return False
    prev = _as_str(command.payload.get("to_version"))
    if not prev:
        _reject(state, command, "missing_target_version")
        return False
    server.version = prev
    return True


def _disable_feature(state: GameState, command: Command) -> bool:
    # MVP: feature flags are modeled only as an ops-complexity relief hook.
    return True


def _pause(state: GameState, command: Command) -> bool:
    state.clock.set_paused(_as_bool(command.payload.get("paused"), True))
    return True


def _set_speed(state: GameState, command: Command) -> bool:
    speed = _as_int(command.payload.get("speed"), 1)
    try:
        state.clock.set_speed(speed)
    except ValueError:
        _reject(state, command, "invalid_speed")
        return False
    return True


_HANDLERS: dict[CommandType, Callable[[GameState, Command], bool]] = {
    CommandType.ADD_NODE: _add_node,
    CommandType.REMOVE_NODE: _remove_node,
    CommandType.CONNECT: _connect,
    CommandType.DISCONNECT: _disconnect,
    CommandType.SET_LB_CONFIG: _set_lb_config,
    CommandType.ENABLE_SERVER: _make_set_server_enabled(True),
    CommandType.DISABLE_SERVER: _make_set_server_enabled(False),
    CommandType.SET_REDIS_CONFIG: _set_redis_config,
    CommandType.SET_DB_POOL: _set_db_pool,
    CommandType.DEPLOY: _deploy,
    CommandType.ROLLBACK: _rollback,
    CommandType.DISABLE_FEATURE: _disable_feature,
    CommandType.PAUSE: _pause,
    CommandType.SET_SPEED: _set_speed,
}

"""Simulation engine — the single public entry point :func:`step`.

Tick pipeline (deterministic; documented in simulation-overview.md):
    1. apply player commands (idempotent)         [once per step]
    for each processed tick:
    2. generate traffic (+ bounded retries)
    3. route via load balancer(s)
    4. process app servers (CPU / memory / queue / timeouts)
    5. process data layer (cache hit/miss, DB pool, DB CPU)
    6. economy (revenue / cost / cash)
    7. collect incident signals -> evaluate incident state machine
    8. apply trust effects
    9. build metric snapshot
    10. build CTO evidence

The engine never mutates the caller's state: it clones the input first and
returns a new state, so ``step`` is pure w.r.t. its arguments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from simulation.commands import Command, apply_commands
from simulation.config.models import BalanceConfig
from simulation.economy.calculator import apply_economy
from simulation.events import DomainEvent, DomainEventType
from simulation.evidence.cto import CTOEvidence, build_cto_evidence
from simulation.incidents.evaluator import evaluate_incidents
from simulation.incidents.rules import collect_signals
from simulation.metrics import MetricSnapshot, build_snapshot
from simulation.nodes.app_server import AppServer
from simulation.nodes.base import Health
from simulation.nodes.postgresql import Postgres
from simulation.requests.generator import generate_count
from simulation.requests.models import TickTraffic
from simulation.requests.router import distribute
from simulation.resources.connection_pool import allocate_connections
from simulation.resources.cpu import cpu_usage
from simulation.resources.memory import memory_usage
from simulation.resources.queue import drain_queue
from simulation.serialization import clone_state
from simulation.state import GameState


@dataclass
class SimulationResult:
    """The output of :func:`step`."""

    state: GameState
    events: List[DomainEvent] = field(default_factory=list)
    snapshot: MetricSnapshot = None  # type: ignore[assignment]
    evidence: CTOEvidence = None  # type: ignore[assignment]


def step(
    state: GameState,
    commands: List[Command],
    config: BalanceConfig,
    ticks: int = 1,
) -> SimulationResult:
    """Advance the simulation by ``ticks`` and return a new state + outputs.

    Determinism: identical (state, commands, config, ticks) always yields an
    identical result.
    """
    work = clone_state(state)
    apply_commands(work, commands)
    event_mark = len(work.events.items)

    last_traffic = TickTraffic()
    for _ in range(max(0, ticks)):
        if not work.clock.is_running():
            break
        work.clock.advance_one()
        last_traffic = _process_tick(work, config)
        signals = collect_signals(work, last_traffic, config)
        evaluate_incidents(work.incidents, signals, work.clock.tick, config, work.events)
        _apply_trust(work, config)

    snapshot = build_snapshot(work, last_traffic)
    evidence = build_cto_evidence(work, snapshot)
    new_events = list(work.events.items[event_mark:])
    return SimulationResult(state=work, events=new_events, snapshot=snapshot, evidence=evidence)


# --------------------------------------------------------------------------- #
# Per-tick pipeline
# --------------------------------------------------------------------------- #


def _process_tick(state: GameState, config: BalanceConfig) -> TickTraffic:
    traffic = TickTraffic()

    retry_in = min(state.pending_retries, config.get_int("retry_ceiling"))
    base = generate_count(state.users, config)
    jitter_amp = config.get_int("traffic_jitter")
    if jitter_amp > 0:
        # Only consumes the RNG when jitter is enabled, so seed affects the run.
        base += state.rng.randint(-jitter_amp, jitter_amp)
    generated = max(0, base) + retry_in
    traffic.generated = generated
    traffic.retried = retry_in

    per_server, routed, dropped = _route(state, generated)
    traffic.per_server_routed = per_server
    traffic.routed = routed
    traffic.dropped_no_server = dropped
    if dropped > 0:
        state.events.emit(
            DomainEvent(state.clock.tick, DomainEventType.REQUEST_DROPPED, detail={"count": dropped})
        )

    processed_total, server_timeouts = _process_servers(state, per_server, config)

    completed, db_timeouts, hits, misses, db_queries = _process_data_layer(
        state, processed_total, config
    )
    traffic.cache_hits = hits
    traffic.cache_misses = misses
    traffic.db_queries = db_queries
    traffic.completed = completed
    traffic.timed_out = server_timeouts + db_timeouts

    # Bounded retries: a fraction of timed-out requests re-enter next tick.
    retry_fraction = config.get("retry_fraction")
    ceiling = config.get_int("retry_ceiling")
    state.pending_retries = min(int(traffic.timed_out * retry_fraction), ceiling)

    apply_economy(state, completed, config)
    return traffic


def _route(state: GameState, generated: int) -> Tuple[Dict[str, int], int, int]:
    per_server: Dict[str, int] = {sid: 0 for sid in state.app_servers}

    if state.load_balancers:
        enabled_lbs = [lb for lb in state.load_balancers.values() if lb.enabled]
        if not enabled_lbs:
            return per_server, 0, generated
        shares = _split_evenly(generated, len(enabled_lbs))
        for lb, share in zip(enabled_lbs, shares):
            servers = state.app_servers_behind(lb.id)
            counts, new_cursor = distribute(lb, servers, share)
            lb.rr_cursor = new_cursor
            for sid, cnt in counts.items():
                per_server[sid] = per_server.get(sid, 0) + cnt
    else:
        # No LB: distribute evenly across available app servers (early game).
        available = [s for s in state.app_servers.values() if s.is_available()]
        if not available:
            return per_server, 0, generated
        shares = _split_evenly(generated, len(available))
        for server, share in zip(available, shares):
            per_server[server.id] = per_server.get(server.id, 0) + share

    routed = sum(per_server.values())
    dropped = generated - routed
    return per_server, routed, dropped


def _split_evenly(total: int, parts: int) -> List[int]:
    if parts <= 0:
        return []
    base = total // parts
    remainder = total % parts
    return [base + (1 if i < remainder else 0) for i in range(parts)]


def _process_servers(
    state: GameState, per_server: Dict[str, int], config: BalanceConfig
) -> Tuple[int, int]:
    drain_rate = config.get_int("app_queue_drain_per_tick")
    timeout_ticks = config.get_int("request_timeout_ticks")
    cpu_cost = config.get("request_cpu_cost")
    mem_cost = config.get("request_mem_cost")

    processed_total = 0
    timeouts_total = 0
    for sid, server in state.app_servers.items():
        assigned = per_server.get(sid, 0)
        if not server.is_available():
            # A down/disabled server does no work: it consumes no CPU. Its queue
            # and memory are frozen until a restart/deploy brings it back.
            server.last_request_rate = 0.0
            server.cpu_usage = 0.0
            continue
        backlog = assigned + server.queue_length
        processed, remaining, timed_out = drain_queue(backlog, drain_rate, timeout_ticks)
        server.queue_length = remaining
        server.last_request_rate = float(assigned)
        server.cpu_usage = cpu_usage(backlog, cpu_cost)
        server.mem_leak_accum = min(1.0, server.mem_leak_accum + server.mem_leak_per_tick)
        server.mem_usage = memory_usage(server.mem_leak_accum, remaining, mem_cost)
        _update_app_health(state, server, config)
        processed_total += processed
        timeouts_total += timed_out
    return processed_total, timeouts_total


def _update_app_health(state: GameState, server: AppServer, config: BalanceConfig) -> None:
    old = server.health
    # Only a genuine memory leak (persistent, monotonic) drives a server DOWN
    # via OOM. Transient queue pressure raises memory toward CRITICAL but does
    # not kill the server, so CPU overload can persist and be observed.
    if server.mem_leak_accum >= 1.0:
        new = Health.DOWN
    else:
        cpu_crit = config.get("app_cpu_critical")
        cpu_warn = config.get("app_cpu_warning")
        mem_crit = config.get("app_mem_critical")
        mem_warn = config.get("app_mem_warning")
        if server.cpu_usage >= cpu_crit or server.mem_usage >= mem_crit:
            new = Health.CRITICAL
        elif server.cpu_usage >= cpu_warn or server.mem_usage >= mem_warn:
            new = Health.WARNING
        else:
            new = Health.HEALTHY
    _emit_health_change(state, server.id, old, new)
    server.health = new


def _process_data_layer(
    state: GameState, processed_total: int, config: BalanceConfig
) -> Tuple[int, int, int, int, int]:
    cacheable_ratio = config.get("cacheable_ratio")
    db_ratio = config.get("db_required_ratio")

    cacheable = int(processed_total * cacheable_ratio)
    noncacheable = processed_total - cacheable

    hits, misses = _process_cache(state, cacheable, config)

    noncacheable_db = int(noncacheable * db_ratio)
    noncacheable_direct = noncacheable - noncacheable_db
    db_demand = misses + noncacheable_db

    db = _first(state.databases)
    if db is None:
        # No DB: everything that needed one is served trivially (early game).
        completed = hits + noncacheable + misses
        return completed, 0, hits, misses, 0

    active, waiting = allocate_connections(db_demand, db.max_connections)
    db.active_connections = active
    db.waiting_connections = waiting
    db.query_queue = waiting
    db.cpu_usage = min(1.0, max(0.0, active * config.get("db_cpu_per_active_conn")))
    _update_db_health(state, db, config)

    if waiting > 0:
        state.events.emit(
            DomainEvent(
                state.clock.tick,
                DomainEventType.CONNECTION_POOL_EXHAUSTED,
                target=db.id,
                detail={"waiting": waiting, "active": active},
            )
        )

    db_served = active
    db_timeouts = waiting
    completed = hits + noncacheable_direct + db_served
    return completed, db_timeouts, hits, misses, db_served


def _process_cache(state: GameState, cacheable: int, config: BalanceConfig) -> Tuple[int, int]:
    cache = _first(state.caches)
    if cache is None or not cache.enabled or cache.ttl_ticks <= 0 or cacheable <= 0:
        if cache is not None:
            cache.hit_rate = 0.0
        return 0, cacheable

    base = config.get("cache_base_hit_rate")
    cache.used_entries = min(cache.capacity_entries, cache.used_entries + cacheable)
    overflow = max(0, cache.used_entries - cache.capacity_entries)
    penalty = min(1.0, overflow / max(1, cache.capacity_entries)) * base
    hit_rate = max(0.0, min(1.0, base - penalty))
    cache.hit_rate = hit_rate

    hits = int(cacheable * hit_rate)
    misses = cacheable - hits
    if hits > 0:
        state.events.emit(
            DomainEvent(state.clock.tick, DomainEventType.CACHE_HIT, target=cache.id,
                        detail={"count": hits})
        )
    if misses > 0:
        state.events.emit(
            DomainEvent(state.clock.tick, DomainEventType.CACHE_MISS, target=cache.id,
                        detail={"count": misses})
        )
    return hits, misses


def _update_db_health(state: GameState, db: Postgres, config: BalanceConfig) -> None:
    old = db.health
    ratio = db.connection_ratio()
    if db.cpu_usage >= config.get("db_cpu_critical") or ratio >= config.get("db_conn_critical"):
        new = Health.CRITICAL
    elif db.cpu_usage >= config.get("db_cpu_warning") or ratio >= config.get("db_conn_warning"):
        new = Health.WARNING
    else:
        new = Health.HEALTHY
    _emit_health_change(state, db.id, old, new)
    db.health = new


def _emit_health_change(state: GameState, node_id: str, old: Health, new: Health) -> None:
    if old == new:
        return
    if new == Health.DOWN:
        state.events.emit(DomainEvent(state.clock.tick, DomainEventType.NODE_DOWN, target=node_id))
    elif new in (Health.WARNING, Health.CRITICAL):
        state.events.emit(
            DomainEvent(state.clock.tick, DomainEventType.NODE_OVERLOADED, target=node_id,
                        detail={"health": new.value})
        )
    elif new == Health.HEALTHY:
        state.events.emit(
            DomainEvent(state.clock.tick, DomainEventType.NODE_RECOVERED, target=node_id)
        )


def _apply_trust(state: GameState, config: BalanceConfig) -> None:
    """Active incidents erode user trust; recovery is handled by resolution."""
    loss_per_tick = config.get("trust_loss_per_incident_tick")
    active_count = sum(
        1 for inc in state.incidents.active.values() if inc.phase.value == "ACTIVE"
    )
    if active_count > 0:
        state.user_trust = max(0.0, state.user_trust - loss_per_tick * active_count)


def _first(collection: Dict[str, "object"]):  # type: ignore[no-untyped-def]
    for value in collection.values():
        return value
    return None

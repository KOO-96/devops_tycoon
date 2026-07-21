"""Simulation engine — the single public entry point :func:`step`.

Tick pipeline (deterministic; documented in simulation-overview.md):
    1. apply player commands (idempotent)         [once per step]
    for each processed tick:
    2. generate traffic (+ bounded retries)
    3. route via load balancer(s)
    4. process app servers (CPU / memory / queue / timeouts)
    5. process the data layer per app's CONNECTED cache/db (cache, pool, DB CPU)
    6. economy (revenue / cost / cash)
    7. collect incident signals -> evaluate incident state machine
    8. apply trust effects
    9. build metric snapshot
    10. build CTO evidence

The engine never mutates the caller's state: it clones the input first and
returns a new state, so ``step`` is pure w.r.t. its arguments. Events produced
during the step are captured in a dedicated sink (not by list index), so they
survive event-log ring-buffer trimming (D1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from simulation.commands import Command, apply_commands
from simulation.config.models import BalanceConfig
from simulation.economy.calculator import apply_economy
from simulation.events import DomainEvent, DomainEventType
from simulation.evidence.cto import CTOEvidence, build_cto_evidence
from simulation.incidents.evaluator import evaluate_incidents
from simulation.incidents.rules import collect_signals
from simulation.metrics import MetricSnapshot, build_snapshot
from simulation.nodes.app_server import AppServer
from simulation.nodes.base import Health, clamp
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
    snapshot: MetricSnapshot
    evidence: CTOEvidence
    events: list[DomainEvent] = field(default_factory=list)


@dataclass
class _DataLayerResult:
    completed: int = 0
    db_timeouts: int = 0
    failed_no_db: int = 0
    hits: int = 0
    misses: int = 0
    db_queries: int = 0
    evictions: int = 0


def step(
    state: GameState,
    commands: list[Command],
    config: BalanceConfig,
    ticks: int = 1,
) -> SimulationResult:
    """Advance the simulation by ``ticks`` and return a new state + outputs.

    Determinism: identical (state, commands, config, ticks) always yields an
    identical result. Negative ``ticks`` is an error; ``ticks == 0`` applies
    commands without advancing time.
    """
    if ticks < 0:
        raise ValueError(f"ticks must be >= 0, got {ticks}")

    work = clone_state(state)
    step_events: list[DomainEvent] = []
    work.events.begin_capture(step_events)
    try:
        apply_commands(work, commands, config)

        last_traffic = TickTraffic()
        for _ in range(ticks):
            if not work.clock.is_running():
                break
            work.clock.advance_one()
            last_traffic = _process_tick(work, config)
            signals = collect_signals(work, last_traffic, config)
            evaluate_incidents(work.incidents, signals, work.clock.tick, config, work.events)
            _apply_trust(work, config)
    finally:
        work.events.end_capture()

    snapshot = build_snapshot(work, last_traffic)
    evidence = build_cto_evidence(work, snapshot)
    return SimulationResult(state=work, events=step_events, snapshot=snapshot, evidence=evidence)


# --------------------------------------------------------------------------- #
# Per-tick pipeline
# --------------------------------------------------------------------------- #


def _process_tick(state: GameState, config: BalanceConfig) -> TickTraffic:
    traffic = TickTraffic()

    retry_in = min(state.pending_retries, config.get_int("retry_ceiling"))
    base = generate_count(state.users, config)
    jitter_amp = config.get_int("traffic_jitter")
    if jitter_amp > 0:
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
            DomainEvent(
                state.clock.tick, DomainEventType.REQUEST_DROPPED, detail={"count": dropped}
            )
        )

    processed, server_timeouts = _process_servers(state, per_server, config)

    data = _process_data_layer(state, processed, config)
    traffic.cache_hits = data.hits
    traffic.cache_misses = data.misses
    traffic.cache_evictions = data.evictions
    traffic.db_queries = data.db_queries
    traffic.completed = data.completed
    traffic.failed = data.failed_no_db
    traffic.timed_out = server_timeouts + data.db_timeouts

    retry_fraction = config.get("retry_fraction")
    ceiling = config.get_int("retry_ceiling")
    state.pending_retries = min(int(traffic.timed_out * retry_fraction), ceiling)

    apply_economy(state, traffic.completed, config)
    return traffic


def _route(state: GameState, generated: int) -> tuple[dict[str, int], int, int]:
    per_server: dict[str, int] = {sid: 0 for sid in state.app_servers}

    if state.load_balancers:
        enabled_lbs = [lb for lb in state.load_balancers.values() if lb.enabled]
        if not enabled_lbs:
            return per_server, 0, generated
        shares = _split_evenly(generated, len(enabled_lbs))
        for lb, share in zip(enabled_lbs, shares, strict=True):
            servers = state.app_servers_behind(lb.id)
            counts, new_cursor = distribute(lb, servers, share)
            lb.rr_cursor = new_cursor
            for sid, cnt in counts.items():
                per_server[sid] = per_server.get(sid, 0) + cnt
    else:
        available = [s for s in state.app_servers.values() if s.is_available()]
        if not available:
            return per_server, 0, generated
        shares = _split_evenly(generated, len(available))
        for server, share in zip(available, shares, strict=True):
            per_server[server.id] = per_server.get(server.id, 0) + share

    routed = sum(per_server.values())
    dropped = generated - routed
    return per_server, routed, dropped


def _split_evenly(total: int, parts: int) -> list[int]:
    if parts <= 0:
        return []
    base = total // parts
    remainder = total % parts
    return [base + (1 if i < remainder else 0) for i in range(parts)]


def _process_servers(
    state: GameState, per_server: dict[str, int], config: BalanceConfig
) -> tuple[dict[str, int], int]:
    """Process each app server; return (per-server processed count, total timeouts)."""
    drain_rate = config.get_int("app_queue_drain_per_tick")
    timeout_ticks = config.get_int("request_timeout_ticks")
    cpu_cost = config.get("request_cpu_cost")
    mem_cost = config.get("request_mem_cost")

    processed_by_server: dict[str, int] = {}
    timeouts_total = 0
    for sid, server in state.app_servers.items():
        assigned = per_server.get(sid, 0)
        if not server.is_available():
            server.last_request_rate = 0.0
            server.cpu_usage = 0.0
            processed_by_server[sid] = 0
            continue
        backlog = assigned + server.queue_length
        processed, remaining, timed_out = drain_queue(backlog, drain_rate, timeout_ticks)
        server.queue_length = remaining
        server.last_request_rate = float(assigned)
        server.cpu_usage = cpu_usage(backlog, cpu_cost)
        server.mem_leak_accum = min(1.0, server.mem_leak_accum + server.mem_leak_per_tick)
        server.mem_usage = memory_usage(server.mem_leak_accum, remaining, mem_cost)
        _update_app_health(state, server, config)
        processed_by_server[sid] = processed
        timeouts_total += timed_out
    return processed_by_server, timeouts_total


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
    state: GameState, processed_by_server: dict[str, int], config: BalanceConfig
) -> _DataLayerResult:
    """Route each app server's processed requests through its CONNECTED data nodes.

    Unconnected caches/DBs are never touched. DB-required requests with no
    reachable datastore FAIL (they are not completed, earn no revenue) — the
    engine does not assume a phantom SQLite (D2, D3).
    """
    cacheable_ratio = config.get("cacheable_ratio")
    db_ratio = config.get("db_required_ratio")

    # Phase 1: per-app split + accumulate cache write demand per connected cache.
    records: list[tuple[int, int, int, str | None, str | None]] = []
    cache_writes: dict[str, int] = {}
    for app_id, processed in processed_by_server.items():
        if processed <= 0:
            continue
        cacheable = int(processed * cacheable_ratio)
        noncacheable = processed - cacheable
        nc_db = int(noncacheable * db_ratio)
        nc_direct = noncacheable - nc_db
        cache, db = state.resolve_data_path(app_id)
        usable = cache is not None and cache.enabled and cache.ttl_ticks > 0
        cid = cache.id if (usable and cache is not None) else None
        did = db.id if db is not None else None
        if cid is not None:
            cache_writes[cid] = cache_writes.get(cid, 0) + cacheable
        records.append((cacheable, nc_db, nc_direct, cid, did))

    # Phase 2: age caches, then compute hit rate + eviction per cache.
    hit_rates, total_evictions = _process_caches(state, cache_writes, config)

    # Phase 3: totals + per-DB demand.
    result = _DataLayerResult(evictions=total_evictions)
    db_demand: dict[str, int] = {}
    direct_complete = 0
    for cacheable, nc_db, nc_direct, cid, did in records:
        direct_complete += nc_direct
        if cid is not None:
            rate = hit_rates.get(cid, 0.0)
            hits = int(cacheable * rate)
            misses = cacheable - hits
        else:
            hits = 0
            misses = cacheable  # no reachable cache -> all need the DB
        result.hits += hits
        result.misses += misses
        db_needed = misses + nc_db
        if did is None:
            result.failed_no_db += db_needed
        else:
            db_demand[did] = db_demand.get(did, 0) + db_needed

    # Phase 4: allocate each DB pool; unconnected DBs receive zero demand.
    for did, db in state.databases.items():
        _allocate_db(state, db, db_demand.get(did, 0), config)
        result.db_queries += db.active_connections
        result.db_timeouts += db.waiting_connections

    # Phase 5: aggregate cache/failure events.
    if result.hits > 0:
        state.events.emit(
            DomainEvent(state.clock.tick, DomainEventType.CACHE_HIT, detail={"count": result.hits})
        )
    if result.misses > 0:
        state.events.emit(
            DomainEvent(
                state.clock.tick, DomainEventType.CACHE_MISS, detail={"count": result.misses}
            )
        )
    if result.failed_no_db > 0:
        state.events.emit(
            DomainEvent(
                state.clock.tick,
                DomainEventType.REQUEST_FAILED,
                detail={"count": result.failed_no_db, "reason": "DATABASE_NOT_CONNECTED"},
            )
        )

    result.completed = result.hits + direct_complete + result.db_queries
    return result


def _process_caches(
    state: GameState, cache_writes: dict[str, int], config: BalanceConfig
) -> tuple[dict[str, float], int]:
    base = config.get("cache_base_hit_rate")
    retention = config.get("cache_retention_ratio")
    penalty = config.get("cache_eviction_hit_penalty")
    hit_rates: dict[str, float] = {}
    total_evictions = 0

    for cid, cache in state.caches.items():
        # Age existing entries so a cache does not stay permanently full.
        cache.used_entries = int(cache.used_entries * retention)
        if not cache.enabled or cache.ttl_ticks <= 0:
            cache.hit_rate = 0.0
            continue
        writes = cache_writes.get(cid, 0)
        if writes <= 0:
            cache.hit_rate = base  # idle but healthy: nothing to serve
            continue

        predicted = cache.used_entries + writes
        overflow = max(0, predicted - cache.capacity_entries)
        cache.used_entries = predicted - overflow  # never exceeds capacity
        churn = overflow / max(1, writes)
        cache.hit_rate = clamp(base * (1.0 - penalty * churn), 0.0, 1.0)
        hit_rates[cid] = cache.hit_rate

        state.events.emit(
            DomainEvent(
                state.clock.tick, DomainEventType.CACHE_WRITE, target=cid, detail={"count": writes}
            )
        )
        if overflow > 0:
            total_evictions += overflow
            state.events.emit(
                DomainEvent(
                    state.clock.tick,
                    DomainEventType.CACHE_EVICTION,
                    target=cid,
                    detail={"count": overflow},
                )
            )
    return hit_rates, total_evictions


def _allocate_db(state: GameState, db: Postgres, demand: int, config: BalanceConfig) -> None:
    active, waiting = allocate_connections(demand, db.max_connections)
    db.active_connections = active
    db.waiting_connections = waiting
    db.query_queue = waiting
    db.cpu_usage = clamp(active * config.get("db_cpu_per_active_conn"), 0.0, 1.0)
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
            DomainEvent(
                state.clock.tick,
                DomainEventType.NODE_OVERLOADED,
                target=node_id,
                detail={"health": new.value},
            )
        )
    elif new == Health.HEALTHY:
        state.events.emit(
            DomainEvent(state.clock.tick, DomainEventType.NODE_RECOVERED, target=node_id)
        )


def _apply_trust(state: GameState, config: BalanceConfig) -> None:
    """Active incidents erode user trust; recovery is handled by resolution."""
    loss_per_tick = config.get("trust_loss_per_incident_tick")
    active_count = sum(1 for inc in state.incidents.active.values() if inc.phase.value == "ACTIVE")
    if active_count > 0:
        state.user_trust = max(0.0, state.user_trust - loss_per_tick * active_count)

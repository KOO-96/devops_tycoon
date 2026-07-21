# Simulation State Model

- Version: v0.1.0
- Status: Draft (for review/devcto)

## GameState

`GameState` (`simulation/state.py`) is the complete, serializable, deterministic
state. Everything needed to resume a run is inside it.

| Field | Type | Notes |
|-------|------|-------|
| `simulation_id` | str | session identifier |
| `version` | int | state schema version (`STATE_VERSION`) |
| `clock` | Clock | tick, tick_ms, speed (0/1/2/4), paused |
| `rng` | Rng | SplitMix64; serialized as a single int (`rng_state`) |
| `users` | int | active user base (traffic source) |
| `load_balancers` | dict[str, LoadBalancer] | algorithm, sticky, rr_cursor |
| `app_servers` | dict[str, AppServer] | cpu/mem/queue/health/version/weight/leak |
| `caches` | dict[str, RedisCache] | hit_rate, ttl, capacity, stale groundwork |
| `databases` | dict[str, Postgres] | pool, active/waiting conn, cpu |
| `connections` | list[(src, dst)] | directed edges (the wiring) |
| `incidents` | IncidentBook | active incidents + per-key cooldowns |
| `events` | EventLog | bounded ring buffer of domain events |
| `applied_command_ids` | list[str] | idempotency ledger |
| `economy` | Economy | cash, revenue, cost (cash may go negative) |
| `user_trust` / `investor_trust` | float | 0..100 |
| `tech_debt` / `ops_complexity` | float | growth hooks |
| `next_request_id` | int | deterministic sample-request ids |
| `pending_retries` | int | bounded retry carry-over (anti-storm) |
| `sample_requests` | list[Request] | bounded visualization sample |

## Key entities

- **AppServer** — `cpu_usage`, `mem_usage` (effective), `mem_leak_accum`
  (persistent leak; only this ≥ 1.0 causes OOM `DOWN`), `queue_length`, `health`
  (`Healthy/Warning/Critical/Down`), `version`, `weight`, `enabled`.
- **LoadBalancer** — `algorithm` (`round_robin/weighted/least_conn`), `sticky`,
  `rr_cursor` (persisted for deterministic round-robin across ticks/restores).
- **RedisCache** — `hit_rate`, `ttl_ticks`, `capacity_entries`, `used_entries`,
  plus `cached_version/source_version/expire_tick` (stale-cache groundwork; no
  invalidation policy is assumed — Event has not confirmed one).
- **Postgres** — single pool (MVP simplification): `max_connections`,
  `active_connections`, `waiting_connections`, `cpu_usage`, `query_queue`.
- **Request / TickTraffic** — a sampled `Request` for tracing; bulk traffic is
  aggregated in `TickTraffic` counters for performance.

## State transitions

- **Node health**: `Healthy → Warning → Critical`, plus `Down` (app OOM from
  leak, or explicitly disabled). Recomputed each tick from CPU/memory/pool ratio.
- **Incident phase**: `WARNING → ACTIVE → RECOVERING → RECOVERED → removed`,
  with a cooldown blocking immediate re-arm. One incident per `(type, target)`.

## Number ranges & invariants

- CPU/memory fractions ∈ [0.0, 1.0]; queue length, connections ∈ ℤ≥0.
- `clamp()` neutralizes NaN and out-of-range values.
- Verified over a 5000-tick run: no NaN/Infinity, no unintended negatives,
  `active_connections ≤ max_connections`, event log ≤ its cap.

## Serialization rules

- `state_to_json` / `state_from_json` (`simulation/serialization.py`) round-trip
  through JSON with `sort_keys=True` for stable output.
- Enums serialize by value; connection tuples serialize as 2-element lists and
  restore as tuples; the RNG serializes as its integer state.
- **Contract**: `serialize → deserialize → continue` is identical to an
  uninterrupted run (verified).

## Seed & RNG

- `Rng` is SplitMix64 with a 64-bit integer state — reproducible and trivially
  serializable. No module-global RNG exists; the only RNG lives in `GameState`.
- The engine draws from it **only** when `traffic_jitter > 0` (default 0), so
  determinism holds with or without jitter and seeds affect runs exactly when
  configured to.

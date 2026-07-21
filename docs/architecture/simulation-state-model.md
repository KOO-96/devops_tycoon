# Simulation State Model

- Version: v0.2.0
- Status: Draft (for review/devcto)
- `STATE_VERSION = 2` (v2 replaced the unbounded command ledger with a sequence
  watermark + bounded recent-id window; older snapshots are rejected).

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
| `caches` | dict[str, RedisCache] | hit_rate, ttl, capacity, used_entries (eviction) |
| `databases` | dict[str, Postgres] | pool, active/waiting conn, cpu |
| `connections` | list[(src, dst)] | directed edges: lb→app, app→cache, app→db, cache→db |
| `incidents` | IncidentBook | active incidents + per-key cooldowns |
| `events` | EventLog | bounded ring buffer (+ transient step capture sink) |
| `recent_command_ids` | list[str] | bounded recent-id window (size from config) |
| `last_applied_command_sequence` | int | monotonic sequence watermark (idempotency) |
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
  aggregated in `TickTraffic` counters for performance (`completed`, `failed`,
  `cache_evictions`, `timed_out`, ...).

## Data-path resolution (D2)

`GameState.resolve_data_path(app_id)` returns the `(cache, db)` an app actually
reaches, following real connections with a visited-set cycle guard:

1. app's directly connected cache;
2. that cache's downstream DB (App → Redis → PostgreSQL);
3. otherwise the app's directly connected DB;
4. otherwise no DB → DB-required requests fail (`REQUEST_FAILED`,
   `DATABASE_NOT_CONNECTED`). The engine never assumes a phantom SQLite.

Unconnected caches/DBs receive zero demand and their CPU/connections/hit rate do
not change.

## Cache capacity & eviction (D4)

Each tick a cache ages `used_entries` by `cache_retention_ratio`, then absorbs
new writes. Overflow beyond `capacity_entries` is evicted (emits
`CACHE_EVICTION`, `used_entries` never exceeds capacity) and eviction pressure
lowers `hit_rate` — so a small cache genuinely differs from a large one.

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
- **Version check**: `from_dict` raises `UnsupportedStateVersionError(expected,
  received)` when the version differs from `STATE_VERSION` (or is missing) — no
  silent partial load (D6).
- **Contract**: `serialize → deserialize → continue` is identical to an
  uninterrupted run (verified), including the command sequence watermark.

## Seed & RNG

- `Rng` is SplitMix64 with a 64-bit integer state — reproducible and trivially
  serializable. No module-global RNG exists; the only RNG lives in `GameState`.
- The engine draws from it **only** when `traffic_jitter > 0` (default 0), so
  determinism holds with or without jitter and seeds affect runs exactly when
  configured to.

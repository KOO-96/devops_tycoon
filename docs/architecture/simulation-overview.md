# Simulation Overview

- Version: v0.2.0 (MVP Simulation Foundation — Ops-review fixes)
- Branch: `agent/simulation`
- Status: Draft (for review/devcto)
- Runtime: Python 3.11+ (verified on 3.12)
- Basis: `docs/game-design/devops-tycoon-master-plan.md`, `docs/game-design/program-decisions.md`,
  `docs/game-design/events/*` (all Approved)

## v0.2 corrections (Ops review)

- **D1 Step events**: events emitted during a step are captured in a dedicated
  sink (`EventLog.begin_capture`/`end_capture`), never inferred from list
  indices, so they survive ring-buffer trimming.
- **D2 Connected data routing**: each app server routes to its *connected*
  cache/DB via `GameState.resolve_data_path`; unconnected nodes are untouched.
- **D3 No phantom datastore**: DB-required requests with no reachable DB emit
  `REQUEST_FAILED` (reason `DATABASE_NOT_CONNECTED`), are not completed, and earn
  no revenue.
- **D4 Cache eviction**: capacity overflow evicts entries and emits
  `CACHE_EVICTION`; capacity affects hit rate; `used_entries <= capacity`.
- **D5 Command idempotency**: sequence watermark + bounded recent-id ledger
  (Backend owns permanent idempotency).
- **D6 State version**: unsupported versions raise `UnsupportedStateVersionError`.
- **D7 Tick args**: negative `ticks` raises `ValueError`; `0` = no advance.

## Responsibility & boundaries

The simulation computes the **facts** of the game and nothing else (master-plan 4.17):

- **Simulation** — request flow, resource usage, incident conditions, technology
  effects, economy, and the **CTO evidence** data. Pure domain logic, no I/O.
- **Backend** — API, WebSocket, persistence. Calls the simulation and stores/forwards
  its output. Does not compute game rules.
- **Frontend** — renders state, sends player input. No game logic.
- **AI CTO** — consumes CTO evidence; may not alter simulation facts (P8).

Forbidden dependencies (enforced by design; verified: stdlib-only): FastAPI,
WebSocket servers, real Redis/PostgreSQL drivers, LLM APIs, wall-clock time,
network, module-global mutable RNG.

## Public interface

```python
from simulation import step            # the only entry point
result = step(state, commands, config, ticks=1)
# result.state     -> new GameState (input is never mutated)
# result.events    -> list[DomainEvent] produced this step
# result.snapshot  -> MetricSnapshot (observable metrics)
# result.evidence  -> CTOEvidence (facts vs hypotheses vs unavailable)
```

`step` clones the input state, so it is pure with respect to its arguments.

## Command processing order

1. Commands are applied **once per step**, in list order, before any tick advances.
2. Idempotency: sequenced commands use a watermark; unsequenced fall back to a
   bounded recent-id window. Duplicates / out-of-order / past sequences are
   rejected without mutating game state (see backend contract).
3. Invalid commands (unknown node, disallowed edge, bad speed) are rejected and
   emit `COMMAND_REJECTED`; valid ones emit `COMMAND_APPLIED`.

## Tick pipeline (per processed tick)

A paused clock (speed 0 or `paused=True`) processes zero ticks.

1. **Generate traffic** — aggregate count from users (+ bounded retries). RNG is
   only drawn when `traffic_jitter > 0`, so seeds matter exactly when configured.
2. **Route** — load balancer distributes to available app servers
   (round-robin / weighted / least-conn; sticky or skewed weights → imbalance).
3. **App servers** — CPU, memory, queue drain, timeouts per server.
4. **Data layer (per connected node)** — each app's processed requests flow
   through its `resolve_data_path` cache (hit/miss/eviction) and DB (pool, CPU).
   DB-required requests with no reachable DB fail (`REQUEST_FAILED`).
5. **Economy** — revenue from completed requests, cost from running nodes, cash.
6. **Incidents** — collect signals from observable metrics → advance the incident
   state machine (WARNING → ACTIVE → RECOVERING → RECOVERED).
7. **Trust** — active incidents erode user trust.
8. **Snapshot + evidence** — build the observable metric snapshot and CTO evidence.

## Domain event vs incident state

- **Domain events** are momentary facts (`CACHE_HIT`, `CACHE_EVICTION`,
  `CONNECTION_POOL_EXHAUSTED`, `REQUEST_FAILED`, `REQUEST_TIMEOUT`). They live in a
  bounded ring buffer (default 500) so long runs never grow unbounded. A step
  additionally returns *all* events it emitted via a capture sink, independent of
  ring-buffer trimming (D1).
- **Incidents** are persistent conditions with a lifecycle, keyed by
  `(type, target)` so the same failure is never re-emitted every tick. Every
  incident passes through `WARNING` before `ACTIVE`, guaranteeing an observable
  warning sign precedes each failure (P7).

## Determinism

Same `(state, commands, config, ticks)` ⇒ identical `result`. Guaranteed by:
a serializable integer RNG state (SplitMix64), tick-only time, no wall-clock, no
hidden globals. Verified: 300-tick runs identical across instances; serialize →
restore → continue equals the uninterrupted run.

## Reproduced incidents (MVP)

LB traffic imbalance, App CPU overload, App memory saturation (leak → DOWN),
DB connection pool exhaustion, DB CPU saturation (P6: enlarging the pool pushes
load to DB CPU), Redis cache-miss spike, request timeout, no-healthy-server.

## Balance values

All thresholds/numbers come from `BalanceConfig` (never hardcoded), each tagged
`Confirmed` / `Proposed` / `TBD` with source and related event id. See
`simulation/config/defaults.py`. Time numbers are Proposed pending playtest;
`db_conn_warning = 0.80` and `max_chain_depth = 4` are Confirmed.

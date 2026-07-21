# Simulation Overview

- Version: v0.1.0 (MVP Simulation Foundation)
- Branch: `agent/simulation`
- Status: Draft (for review/devcto)
- Basis: `docs/game-design/devops-tycoon-master-plan.md`, `docs/game-design/program-decisions.md`,
  `docs/game-design/events/*` (all Approved)

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
2. Each command id is recorded; a duplicate id is rejected without mutating game
   state (idempotency, sim prompt §11).
3. Invalid commands (unknown node, disallowed edge, bad speed) are rejected and
   emit `COMMAND_REJECTED`; valid ones emit `COMMAND_APPLIED`.

## Tick pipeline (per processed tick)

A paused clock (speed 0 or `paused=True`) processes zero ticks.

1. **Generate traffic** — aggregate count from users (+ bounded retries). RNG is
   only drawn when `traffic_jitter > 0`, so seeds matter exactly when configured.
2. **Route** — load balancer distributes to available app servers
   (round-robin / weighted / least-conn; sticky or skewed weights → imbalance).
3. **App servers** — CPU, memory, queue drain, timeouts per server.
4. **Data layer** — cache hit/miss, then DB connection pool allocation and DB CPU.
5. **Economy** — revenue from completed requests, cost from running nodes, cash.
6. **Incidents** — collect signals from observable metrics → advance the incident
   state machine (WARNING → ACTIVE → RECOVERING → RECOVERED).
7. **Trust** — active incidents erode user trust.
8. **Snapshot + evidence** — build the observable metric snapshot and CTO evidence.

## Domain event vs incident state

- **Domain events** are momentary facts (`CACHE_HIT`, `CONNECTION_POOL_EXHAUSTED`,
  `REQUEST_TIMEOUT`). They live in a bounded ring buffer (default 500) so long runs
  never grow unbounded.
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

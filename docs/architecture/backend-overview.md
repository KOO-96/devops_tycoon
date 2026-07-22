# Backend Overview

- Version: v0.1.0 (MVP Game Session API Foundation)
- Branch: `agent/backend`
- Status: Draft (for review/devcto)
- Runtime: Python 3.11+ (verified on 3.12)

## Purpose

Expose the pure `simulation` engine as a game-session API: create sessions,
apply player commands (idempotent, sequenced, revision-locked), advance ticks,
query/stream domain events. The backend owns all I/O; the simulation stays a
pure domain module.

## Layers & boundaries

```
API (FastAPI routes + schemas)      # HTTP/WS, validation, error envelope
  -> Application services            # session/command/event use-cases, transactions
     -> Simulation Adapter           # Backend <-> simulation translation ONLY here
     -> Persistence (UnitOfWork)     # PostgreSQL (prod) | in-memory (dev/test)
     -> Event Broker                 # Redis (prod) | in-memory (dev/test); transport only
```

- Only `backend/adapters/simulation_adapter.py` imports `simulation`. Backend
  never mutates simulation internals or state facts.
- Application services depend on repository/UoW **protocols**, not concrete
  storage. `storage_backend`/`event_broker` settings pick the implementation.
- The simulation package has **zero** backend dependencies (enforced: separate
  optional-dependency group; simulation imports only stdlib).

## Storage selection

| Setting | Value | Use |
|---------|-------|-----|
| `DEVOPS_TYCOON_STORAGE_BACKEND` | `memory` (default) / `postgres` | source of truth |
| `DEVOPS_TYCOON_EVENT_BROKER` | `memory` (default) / `redis` | live fan-out transport |

`memory` needs no external services (local/dev/test). `postgres`+`redis` are the
production path (PostgreSQL is the durable source of truth; Redis is transport).

## Public simulation entry points used

`simulation.step`, `state_to_json`/`state_from_json`, `factory.new_state`,
`GameState.from_dict`, `UnsupportedStateVersionError`, `STATE_VERSION`.

## Tick advance

No production auto-tick scheduler in this PR (deferred). State advances through
the explicit application service `advance_session`, exposed only via the
development-only `/internal/v1/.../advance` endpoint
(`ENABLE_MANUAL_TICK_API`, default **false**).

## Health

- `GET /health/live` — liveness; never fails due to external stores.
- `GET /health/ready` — checks broker + storage + supported `STATE_VERSION`.

## Follow-ups handled / deferred

Handled: SIM-FU-001 (strict ticks), BACK-FU-001 (idempotency store), BACK-FU-002
(session serialization), BACK-FU-003 (error schema), BACK-FU-005 (event id +
cursor). Deferred: BACK-FU-004 (snapshot cadence/migration/transport
optimization), BACK-FU-006 (event payload enrichment), SIM-FU-002~004,
authentication/session-ownership (see backend-error-contract.md and
backend-persistence.md).

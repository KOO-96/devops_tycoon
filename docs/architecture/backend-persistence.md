# Backend Persistence

- Version: v0.1.0 · Status: Draft (for review/devcto)

PostgreSQL is the durable **source of truth**. Redis is a transport only.

## Tables (Alembic `0001_initial`)

**game_sessions** — `id` (UUID PK), `status`, `simulation_state` (JSONB),
`simulation_state_version`, `revision` (BIGINT), `next_command_sequence` (BIGINT),
`created_at`, `updated_at`.

**game_commands** — `id` (**surrogate UUID primary key**), `session_id` (FK),
`command_id` (client idempotency key), `sequence`, `command_type`, `payload_hash`,
`status`, `result` (JSONB), `created_at`, `completed_at`. Constraints:
`PRIMARY KEY(id)`, `UNIQUE(session_id, command_id)`, `UNIQUE(session_id, sequence)`,
index on `session_id`. **`command_id` has no global unique/PK constraint** — it is
unique only within a session (HIGH-3), so two sessions may reuse the same
`command_id` independently.

**game_events** — `cursor` (BIGINT Identity PK), `event_id` (UNIQUE), `session_id`
(FK), `session_revision`, `tick`, `event_type`, `target`, `payload` (JSONB),
`created_at`. Indexes on `session_id` and `(session_id, cursor)`.

Migrations provide upgrade + downgrade. The app never auto-migrates; migrations
run via an explicit ops command (`alembic upgrade head`).

## Event cursor semantics (LOW-1)

`cursor` is a **globally monotonic** BIGINT identity across the whole event store,
not a per-session counter starting at 1. Within a single session the cursor is
strictly increasing but **may have gaps** (numbers consumed by other sessions'
events). A gap is **not** a missing event. Clients replay with
`(session_id, after_cursor)` where `after_cursor` is exclusive, and de-duplicate
by `event_id` and/or `cursor`.

### Pagination (`GET /events`)

- `after_cursor` is **exclusive** (returns events with `cursor > after_cursor`);
  default `0`.
- `limit` default **100**, capped at **1000** (`events_page_default` /
  `events_page_max`; the service clamps over-large values).
- Results are ordered by ascending `cursor`.
- If the returned count **equals the effective limit**, more events may exist:
  request the next page with `after_cursor` = the last returned event's `cursor`.
- A session's cursors ascend but may have **gaps** (numbers consumed by other
  sessions) — a gap is not a lost event.
- The response is `{session_id, events[]}`. `next_cursor`/`has_more` are a possible
  future addition (BACK-FU); for now derive paging from the rules above.

## Idempotency (BACK-FU-001)

- Backend assigns `sequence` and persists permanent results in `game_commands`
  under a **surrogate UUID `id`**; `command_id` is the client idempotency key,
  scoped to a session. **Idempotency look-ups always key on
  `(session_id, command_id)`**, never `command_id` alone — different sessions may
  reuse the same `command_id` (HIGH-3).
- The idempotency **request hash** = `command_type` + canonical `payload` (excludes
  `expected_revision`, request id, timestamps, and the backend `sequence`).
- Look-up precedes the revision check: same `(session_id, command_id)` + same request
  hash → original stored result (no re-run), even if `expected_revision` is stale (HIGH-1).
- Same `(session_id, command_id)` + different `command_type`/payload → `IDEMPOTENCY_CONFLICT`
  (scoped to that session only).
- `UNIQUE(session_id, command_id)` and `UNIQUE(session_id, sequence)` guard against
  duplicates under races (verified with concurrent same-id requests on real PG).
- The simulation additionally keeps its own sequence watermark + bounded recent
  ledger inside the snapshot; the DB `game_commands` table is the permanent record.

## Concurrency (BACK-FU-002)

Correctness source of truth is the DB transaction. `get_for_update` takes
`SELECT ... FOR UPDATE` on the session row; sequence allocation, snapshot write,
and event append happen inside that one transaction. The in-memory backend
mirrors this with a per-session lock held for the UnitOfWork and atomic
apply-on-commit / discard-on-rollback. On conflict or persist failure the whole
transaction rolls back — a partially applied state is never saved.

## Snapshot policy (BACK-FU-004 — partly deferred)

This foundation saves the full latest snapshot after every state change (with
its `revision` and `simulation_state_version`). Deferred: historical snapshot
retention cadence, delta transport, and migration tooling for future
`STATE_VERSION` bumps (owner: Backend; next storage-layer PR).

## State version

`simulation_state_version` is stored and validated on restore; a mismatch raises
`UnsupportedStateVersionError` → `SNAPSHOT_VERSION_UNSUPPORTED` (never a silent
partial load). Old snapshots require migration, not blind load.

## Running the integration tests

The `-m integration` suite requires real PostgreSQL 16 and Redis 7 and is
skipped otherwise. Provide connection URLs (do not commit them):

```
export DEVOPS_TYCOON_TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
export DEVOPS_TYCOON_TEST_REDIS_URL=redis://host:6379/0
pytest -q -m integration
```

Example services (ephemeral):

```
docker run -d --name dt-pg  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=devops_tycoon_test -p 5432:5432 postgres:16-alpine
docker run -d --name dt-rd  -p 6379:6379 redis:7-alpine
```

Schema is created once per session via Alembic and torn down via
`alembic downgrade base`; each test `TRUNCATE ... RESTART IDENTITY CASCADE`s the
tables and never leaves `alembic_version` stale (the suite is safe to run
consecutively; `metadata.drop_all` is not used for cleanup).

### INFRA-FU-001 (owner: Infra/Platform)

Add PostgreSQL 16 + Redis 7 service containers to PR CI and make
`pytest -m integration` a required gate. This Backend PR does not modify CI/k3s.

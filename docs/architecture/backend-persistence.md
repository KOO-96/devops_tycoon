# Backend Persistence

- Version: v0.1.0 · Status: Draft (for review/devcto)

PostgreSQL is the durable **source of truth**. Redis is a transport only.

## Tables (Alembic `0001_initial`)

**game_sessions** — `id` (UUID PK), `status`, `simulation_state` (JSONB),
`simulation_state_version`, `revision` (BIGINT), `next_command_sequence` (BIGINT),
`created_at`, `updated_at`.

**game_commands** — `id`, `session_id` (FK), `command_id`, `sequence`,
`command_type`, `payload_hash`, `status`, `result` (JSONB), `created_at`,
`completed_at`. Constraints: `UNIQUE(session_id, command_id)`,
`UNIQUE(session_id, sequence)`, index on `session_id`.

**game_events** — `cursor` (BIGINT Identity PK), `event_id` (UNIQUE), `session_id`
(FK), `session_revision`, `tick`, `event_type`, `target`, `payload` (JSONB),
`created_at`. Indexes on `session_id` and `(session_id, cursor)`.

Migrations provide upgrade + downgrade. The app never auto-migrates; migrations
run via an explicit ops command (`alembic upgrade head`).

## Idempotency (BACK-FU-001)

- Backend assigns `sequence` and persists permanent results in `game_commands`.
- Same `command_id` + same `payload_hash` → stored result returned (no re-run).
- Same `command_id` + different payload → `IDEMPOTENCY_CONFLICT`.
- `UNIQUE(session_id, sequence)` guards against duplicate sequence under races.
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

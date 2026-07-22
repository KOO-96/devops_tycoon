# Backend Session Lifecycle

- Version: v0.1.0 · Status: Draft (for review/devcto)

## Create

`POST /api/v1/game-sessions` `{seed, users?}` → the adapter builds an initial
`GameState` (STATE_VERSION 2), stored as `revision=0`, `next_command_sequence=1`.
Full BalanceConfig override by external callers is not allowed (only seed/users).

## Command transaction (POST /commands)

Order (one logical transaction; see command_service.py):

1. open UnitOfWork
2. `get_for_update(session)` — row lock (PostgreSQL `FOR UPDATE`; in-memory
   per-session lock held for the UoW)
3. **look up existing `command_id` FIRST** (idempotency precedes the revision check):
   - same request hash → return the **original stored result**, do NOT re-run
     simulation, do NOT check revision (even if `expected_revision` is now stale)
   - different request hash → `IDEMPOTENCY_CONFLICT`
4. **only for a new command**: check `expected_revision` (if given) →
   `REVISION_CONFLICT` on mismatch
5. allocate `sequence = next_command_sequence` (backend-issued; clients never send it)
6. adapter converts to a simulation `Command` and runs `step(..., ticks=0)`
7. validate/serialize new snapshot (JSON-safe, NaN/Inf-free)
8. `revision += 1`; persist snapshot, `next_command_sequence = sequence+1`
9. build event records (backend `event_id`, `session_revision`, cursor at commit)
10. persist command result + session + events
11. **commit**
12. **publish** envelopes to the broker (only after commit)

> The request hash covers `command_type` + canonical `payload` only; it excludes
> `expected_revision`, request id, timestamps, and the backend-issued `sequence`.
> Thus the same logical command retried with a *new* `expected_revision` still
> returns the stored result, while the same `command_id` with a different
> `command_type` (or payload) is an `IDEMPOTENCY_CONFLICT` (HIGH-1 fix).

A simulation-valid rejection (e.g. bad target) still consumes the sequence and
is persisted with `status = COMMAND_REJECTED` and a `reason_code` (HTTP 200). An
unknown command *type* fails validation before the simulation runs and does not
consume a sequence (HTTP 422 `COMMAND_REJECTED`).

## Command result statuses

Structured (never parse prose): `APPLIED`, `COMMAND_REJECTED` (+`reason_code`).
Idempotent replays return the stored result. Sequence/revision are always in the
response.

## Manual advance (dev only)

`POST /internal/v1/game-sessions/{id}/advance` `{ticks, expected_revision?}` runs
the same lock→revision→simulation→persist→commit→publish flow with `ticks>0`.
Disabled by default (`MANUAL_TICK_DISABLED`). `ticks` is a strict non-negative
integer within `max_ticks_per_request` (bool/str/negative rejected — SIM-FU-001).

## Read paths

- `GET /game-sessions/{id}` — compact summary (tick, revision, economy, incidents).
- `GET /game-sessions/{id}/snapshot` — full simulation snapshot (+ version).
- `GET /game-sessions/{id}/events?after_cursor&limit` — durable event cursor page.

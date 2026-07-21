# Simulation ↔ Backend Contract

- Version: v0.2.0
- Status: Draft (for review/devcto)
- Runtime: Python 3.11+

> This documents the **domain input/output requirements** of the simulation.
> It does not fix the public API/WebSocket schema — Backend owns that draft
> (master-plan GD-010). Simulation states what it needs and what it returns.

## What Backend passes IN

`step(state, commands, config, ticks)`:

| Input | Meaning |
|-------|---------|
| `state` | prior `GameState` (from a new session or restored from storage) |
| `commands` | ordered `list[Command]` received from players since last step |
| `config` | `BalanceConfig` (may be the default or an override set) |
| `ticks` | how many ticks to process this call (0 = apply commands only) |

`Command` fields: `id` (idempotency key), `type`, `target`, `payload`, `request_tick`,
`sequence` (Backend-assigned).

### `ticks` input validation (Backend responsibility — SIM-FU-001)

Backend MUST reject boolean values for `ticks` even though Python treats `bool`
as a subtype of `int`. Public REST and WebSocket schemas must accept only a
**strict non-negative integer within the configured batch limit**:

- validate `ticks` as a strict integer (reject `bool`);
- reject `ticks < 0` (Simulation also raises `ValueError`, but Backend rejects
  earlier at the API boundary);
- cap the maximum `ticks` per call via Backend configuration so an external
  caller cannot request an unbounded batch;
- large/long-running tick batches are Backend-internal or admin-only, never a
  raw client input.

Simulation currently rejects negative `ticks` (`ValueError`) and treats `0` as
"apply commands only". Adding a `bool` guard inside Simulation is an optional
follow-up; the authoritative input validation is Backend's.

## What Simulation returns OUT

`SimulationResult`:

| Output | Meaning | Backend action |
|--------|---------|----------------|
| `state` | new authoritative `GameState` | persist; treat as source of truth |
| `events` | `list[DomainEvent]` from this step | forward over WebSocket |
| `snapshot` | `MetricSnapshot` (observable metrics) | forward to Frontend |
| `evidence` | `CTOEvidence` | pass to the AI CTO layer (facts only) |

Backend must **not** recompute or mutate any of these values.

## Command idempotency (D5 — DevCTO decision)

Ownership boundary:

- **Backend owns permanent idempotency.** It assigns each command a monotonic
  `sequence` (per session) and persists its own idempotency results.
- **Simulation keeps a sequence watermark** (`last_applied_command_sequence`)
  plus a **bounded recent-id ledger** (`recent_command_ids`, size from
  `command_ledger_size`). The watermark blocks re-application even after an id
  ages out of the bounded window; the recent ledger is for short-term debugging /
  duplicate replies.

Sequence policy (`Command.sequence >= 0`):

| Condition | Result (`COMMAND_REJECTED.reason`) | Sequence consumed? |
|-----------|-------------------------------------|--------------------|
| `sequence < expected` | `already_applied` | no |
| `sequence > expected` | `command_out_of_order` | **no** (may arrive later) |
| `sequence == expected` | applied (success or valid rejection) | **yes** |
| duplicate `id` in window | `duplicate_command_id` | no |

- A command that passes format/target validation consumes its sequence whether
  the handler succeeds or is validly rejected. Undeserializable commands must be
  rejected by Backend before reaching the simulation.
- `sequence < 0` (unsequenced) falls back to best-effort id dedup within the
  recent window only — sequenced commands are authoritative.
- The watermark and recent ledger survive save/restore.

## Session concurrency (Backend responsibility — BACK-FU-002)

Simulation does **not** guarantee safety for concurrent execution against the
same `GameState`. Backend MUST serialize state transitions per game session:

- serialize all command processing for a session (a session lock **or**
  optimistic revision check on the state's tick / `STATE_VERSION`);
- allocate `command_sequence` inside that same serialization boundary;
- treat **command apply → simulation `step` → snapshot persist** as one logical
  transaction; on conflict or persist failure, do **not** save a partially
  applied state as a valid snapshot (`step` already returns a new state and never
  mutates the input, so discarding the result on failure is safe);
- handle REST retries and WebSocket re-sends via the Backend permanent
  idempotency record (see above), not by re-running `step`.

> Backend MUST serialize state transitions per game session. Command sequence
> allocation, simulation execution, and snapshot persistence must occur under one
> lock or optimistic revision boundary.

## Error handling

- Validation failures do not raise; they emit `COMMAND_REJECTED` events with a
  machine-readable `reason` (e.g. `connection_not_allowed`, `invalid_speed`,
  `node_not_found`). Backend surfaces these; game state stays consistent.
- DB-required requests with no reachable datastore emit `REQUEST_FAILED`
  (`reason = DATABASE_NOT_CONNECTED`); they are not completed and earn no revenue.
- The engine **raises** on: unknown balance key (`with_overrides`), unsupported
  state version (`UnsupportedStateVersionError`), and negative `ticks`
  (`ValueError`). It never raises on player input.

## Save / restore

- Persist `state_to_json(state)`; restore with `state_from_json(text)`.
- Restoring and continuing is guaranteed identical to never having stopped.
- Recommended cadence: persist the returned `state` after each `step`
  (or every N ticks); it is ~40 KB JSON for a small cluster after 5000 ticks.

## Versioning

- `GameState.version` (`STATE_VERSION`, currently **2**) tags the state schema.
  Loading a snapshot whose version differs raises `UnsupportedStateVersionError`
  (with `expected`/`received`) — Backend must migrate rather than load blindly.
- The public API should carry its own version prefix (Backend-owned, GD-010).

## Boundary reminders

- Simulation performs **no** I/O: Backend owns all API/WebSocket/DB/Redis/LLM.
- Balance numbers live in `BalanceConfig`; Backend may supply an override set,
  but Proposed/TBD status and provenance should be preserved for observability.
- CTO evidence separates `confirmed_facts` from `hypotheses` and lists
  `unavailable_information`; the AI CTO must not present hypotheses as confirmed
  (master-plan 4.12, P8).

## Non-blocking follow-ups (NOT implemented in this Foundation)

These are tracked items, not completed features. They do not block the MVP
Simulation Foundation.

| ID | Item | Owner | When |
|----|------|-------|------|
| SIM-FU-001 | Reject boolean/invalid `ticks` at external input | Backend | Backend API |
| SIM-FU-002 | Document `cache_retention_ratio=1.0` thrashing boundary | Simulation | Balance tuning |
| SIM-FU-003 | Stale Cache / Cache Stampede key-level lifecycle | Event + Simulation | Later sim PR |
| SIM-FU-004 | Wire `trust_loss_cap_per_incident` once EVT-D-005 is Confirmed | Program + Simulation | After Program decision |
| BACK-FU-001 | Permanent command idempotency store (unique constraint / table) | Backend | Backend foundation |
| BACK-FU-002 | Per-session lock or optimistic revision | Backend | Backend foundation |
| BACK-FU-003 | REST / WebSocket error schema mapping | Backend | API contract |
| BACK-FU-004 | Snapshot cadence, migration, and transport (snapshot vs delta) policy | Backend | Storage layer |
| BACK-FU-005 | Domain event dedup identifier (`event_id`/`sequence`) | Backend (+ optional Simulation) | WebSocket layer |
| BACK-FU-006 | Event enrichment: `REQUEST_FAILED` node target; `CACHE_EVICTION` capacity/used/cause; TTL-vs-capacity distinction | Backend + Simulation | Contract extension |

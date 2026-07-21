# Simulation ↔ Backend Contract

- Version: v0.1.0
- Status: Draft (for review/devcto)

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

`Command` fields: `id` (idempotency key), `type`, `target`, `payload`, `request_tick`.

## What Simulation returns OUT

`SimulationResult`:

| Output | Meaning | Backend action |
|--------|---------|----------------|
| `state` | new authoritative `GameState` | persist; treat as source of truth |
| `events` | `list[DomainEvent]` from this step | forward over WebSocket |
| `snapshot` | `MetricSnapshot` (observable metrics) | forward to Frontend |
| `evidence` | `CTOEvidence` | pass to the AI CTO layer (facts only) |

Backend must **not** recompute or mutate any of these values.

## Command idempotency

- A command `id` is applied at most once. Re-sending the same `id` is safe and
  yields `COMMAND_REJECTED` with reason `duplicate_command_id`; game state is
  unchanged.
- Backend should therefore assign a stable id per player action and may retry
  delivery freely.

## Error handling

- Validation failures do not raise; they emit `COMMAND_REJECTED` events with a
  machine-readable `reason` (e.g. `connection_not_allowed`, `invalid_speed`,
  `node_not_found`). Backend surfaces these; game state stays consistent.
- The engine raises only on programmer error (e.g. an unknown balance key via
  `with_overrides`), never on player input.

## Save / restore

- Persist `state_to_json(state)`; restore with `state_from_json(text)`.
- Restoring and continuing is guaranteed identical to never having stopped.
- Recommended cadence: persist the returned `state` after each `step`
  (or every N ticks); it is ~40 KB JSON for a small cluster after 5000 ticks.

## Versioning

- `GameState.version` (`STATE_VERSION`) tags the state schema. On a bump,
  Backend migrates persisted snapshots; the simulation reads `version` on load.
- The public API should carry its own version prefix (Backend-owned, GD-010).

## Boundary reminders

- Simulation performs **no** I/O: Backend owns all API/WebSocket/DB/Redis/LLM.
- Balance numbers live in `BalanceConfig`; Backend may supply an override set,
  but Proposed/TBD status and provenance should be preserved for observability.
- CTO evidence separates `confirmed_facts` from `hypotheses` and lists
  `unavailable_information`; the AI CTO must not present hypotheses as confirmed
  (master-plan 4.12, P8).

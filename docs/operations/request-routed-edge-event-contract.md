# REQUEST_ROUTED Edge Event Contract (POLICY-C-FU-002 Mapping Prerequisite)

Status: **EVENT_DERIVED_MAPPING_PRECONDITION_READY** — backend/simulation only.
This document records the source→target routing event that a later EVENT_DERIVED
effect lifecycle (POLICY-C-FU-002) will map onto the `effect.network-flow.primary`
visual. **No effect is wired here.** No asset, frontend, or backend-API change.

## Why this exists

FU-002 (`event → effect` lifecycle) was reported
`BLOCKED_ON_EVENT_MAPPING_PRECONDITION`: the simulation emitted no event carrying
a `(source_node, target_node)` pair, so a per-edge flow effect had nothing
deterministic to bind to. Every existing event was single-node (`REQUEST_DROPPED`
count, `NODE_*`, `CACHE_*`, `INCIDENT_*`) and `REQUEST_ROUTED` / `REQUEST_COMPLETED`
were declared-but-dead. This change activates the existing `REQUEST_ROUTED` enum
member (no new enum) to publish the routing topology the effect needs — and
nothing more.

## Contract

The simulation emits **one aggregated `REQUEST_ROUTED` DomainEvent per
`(tick, source_node_id, target_node_id)`** at the authoritative routing point.

| Field | Value |
| --- | --- |
| `type` | `REQUEST_ROUTED` (existing enum member, reused) |
| `tick` | the tick in which the routing decision was made |
| `target` | `target_node_id` (mirrors the edge target; no top-level schema change) |
| `detail.source_node_id` | the routing node that made the decision (the load balancer) |
| `detail.target_node_id` | the app server that received the requests |
| `detail.count` | integer ≥ 1 — requests **actually routed** on that edge this tick |

### Authoritative emission point

`simulation/engine.py::_route` is the single place the simulation *decides*
source→target routing: an enabled load balancer distributes its share across the
app servers connected to it (`distribute(lb, servers, share)`). The per-edge
counts produced there are surfaced as `edge_routed = [(lb.id, server.id, count)]`
and emitted in `_process_tick`, immediately alongside the existing
`REQUEST_DROPPED` emission. The event is **not** inferred on the frontend, **not**
derived from a command, and **not** synthesized from a UI action.

### Aggregation identity — PER_TICK_PER_EDGE

`detail.count` is the aggregate of all requests routed on that edge in that tick,
**not** one event per request. A tick that routes 30,000 requests across 3 edges
emits **3** events (10,000 each), never 30,000. This is the property the effect
layer relies on to bound its work to the topology, not to traffic volume.

### Exclusions and edge cases

- **Zero traffic** (`generated == 0`) → no `REQUEST_ROUTED` events.
- **Fully dropped** (no available server / no enabled LB) → no `REQUEST_ROUTED`;
  the existing `REQUEST_DROPPED` event still fires unchanged.
- **Unavailable / zero-count edge** → omitted (only `count ≥ 1` edges emit).
- **Direct fallback** (no load balancer) has no routing *source* node and a real
  source→target connection edge does not exist, so it contributes no event.
- **Topology validity**: every emitted `(source_node_id, target_node_id)` is a
  real entry in `state.connections`.

### Determinism & non-interference (observation-only)

- **No new RNG**: `distribute` is a pure deterministic function; emission reads no
  randomness. The RNG stream is byte-identical with and without the events
  (`test_emission_does_not_perturb_rng_or_traffic`).
- **No simulation feedback**: emitting the event does not mutate node state,
  traffic, economy, or health. Snapshots are identical across identical runs.
- **Deterministic ordering**: events within a tick follow load-balancer order then
  connection order of the servers behind each LB.
- **A/B replay**: identical `(state, commands, config, ticks)` yields an identical
  `REQUEST_ROUTED` sequence (tick, source, target, count).
- `REQUEST_COMPLETED` remains **dead** (not activated by this change).
- `REQUEST_DROPPED` / `REQUEST_FAILED` / all other events are unchanged.

## Evidence

- Unit + high-load tests: `tests/simulation/test_request_routed_event.py` (14 tests).
  - per-edge emission, detail shape, `target == target_node_id`, count ≥ 1 integer;
  - counts sum to routed traffic; independent per-edge counts;
  - real-connection topology validity;
  - zero-traffic → none; all-dropped → none (+ `REQUEST_DROPPED` intact);
  - unavailable edge excluded, others unaffected;
  - **high-load aggregation**: 30,000 requests → 3 events (PER_TICK_PER_EDGE);
  - deterministic ordering; A/B replay identical;
  - RNG/snapshot unchanged (observation-only); `REQUEST_COMPLETED` stays dead.
- Full regression: `ruff check` clean, `ruff format` clean,
  `mypy simulation backend tests tools` → no issues (129 files),
  `pytest -m "not integration"` → **193 passed, 15 deselected** (was 179; +14).
- Asset gate untouched: `asset-production-gate: PASS 26/26`,
  `verify-generated: nondeterministic=0 schema=0 drift=0 gate=pass`,
  included set = 5, `build_id 0633e0f8…`, C17 = 21,510 B, C18 = 5 MiB. No asset,
  manifest, or `frontend/src` file changed (`git status` shows only
  `simulation/engine.py` + the new test).

## Scope boundary

- **EVENT_DERIVED: NOT_IMPLEMENTED.** This is only the routing *contract* the
  effect will later consume. This backend work does **not** mark FU-002 complete.
- No `#006` asset, no atlas, no particle engine, no TTL/timer, no
  event-name-guess asset lookup, no DomainEvent top-level schema redesign.
- Next step (separate, gated task): FU-002 maps `REQUEST_ROUTED` →
  `effect.network-flow.primary` lifecycle, only after this prerequisite is
  promoted to `dev` by DevCTO review.

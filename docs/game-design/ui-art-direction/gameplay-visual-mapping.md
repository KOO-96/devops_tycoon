# Gameplay ↔ Visual Mapping

- Owner: Program · Status: node/command set = Confirmed; visual treatment = Proposed

Maps the **implemented** Simulation/Backend contract to on-screen objects so the board is
never mere decoration. The Backend snapshot `nodes` + `connections` are the board's source
of truth (Confirmed, already wired in the Frontend Foundation).

## Functional node → building

| Node kind (Confirmed) | Building (Proposed) | Silhouette cue | Must read as |
|---|---|---|---|
| `load_balancer` | Routing Tower | tall tower with fan-out gates/arms | a distributor of traffic |
| `app_server` | Application Workshop | small workshop/office, numbered | one of many workers |
| `redis` | Cache Station | compact, "fast/temporary" motif | speed, volatile store |
| `postgresql` | Data Vault | large vault/data-center | durable, heavy store |

`app_server` buildings must stay distinguishable when many exist (number/label + slight
tier variation). Redis and PostgreSQL must never be confusable.

## Command → visual feedback (all 14 Confirmed commands)

Every state-changing command re-fetches the snapshot, so the board reflects the result
without reload (implemented). Visual feedback (Proposed):

| Command | On-board feedback |
|---|---|
| ADD_NODE | building appears on its tile (build-in effect in P2) |
| REMOVE_NODE | building removed; its lines removed; selection cleared |
| CONNECT | new connection line appears between the two buildings |
| DISCONNECT | connection line disappears |
| SET_LB_CONFIG | routing tower shows algorithm/sticky indicator |
| ENABLE_SERVER | app building returns to active (full saturation) |
| DISABLE_SERVER | app building shows Disabled (desaturated, pause icon) |
| SET_REDIS_CONFIG | cache station shows ttl/capacity indicator |
| SET_DB_POOL | data vault shows pool-size indicator |
| DEPLOY | app building plays Deploy animation (P2); version badge updates |
| ROLLBACK | app building plays Rollback animation (P2); version badge updates |
| DISABLE_FEATURE | subtle flag indicator (ops-relief; minimal visual) |
| PAUSE | global HUD pause state; board activity idles |
| SET_SPEED | global HUD speed; flow animation rate scales (1×/2×/4×) |

DEPLOY/ROLLBACK act on an existing App building in the MVP (no separate CI/CD facility yet).

## Request / data flow (Proposed, Visual MVP)

Represent request flow as small packets / light pulses traveling along connection lines
from Routing Tower → App → Cache/DB, at a rate that scales with speed. This is a **visual
approximation** driven by domain events (e.g. REQUEST_*), not a client-side simulation —
the client computes no ticks. Volume/precision of the flow is Proposed (UI-D-011).

## Incident mapping (Confirmed data; Proposed visuals)

Incidents come from the backend (`active_incidents`: `type`, `target`, `phase`). The board
marks the **target** node with an alert overlay; the right panel lists incidents verbatim.
The Frontend never invents a cause or predicts an outcome (Confirmed boundary).

**Health and incidents are separate.** A node's health badge (or `not_applicable`/
`not_reported` for kinds like load_balancer that omit health) is independent of any
incident overlay. A missing health is never rendered as Healthy and is never
auto-promoted to Critical because an incident exists; conversely an active incident
is never hidden behind a health badge. Example: a load_balancer shows `Health N/A`
in its status while simultaneously showing an `LB_IMBALANCE` incident.

## Functional vs decorative (Confirmed principle)

Only functional objects (the 4 building kinds, real connections, incident targets, request
flow) are interactive and bound to state. Decorative objects (characters, benches, roads,
signage, vehicles, lab backdrops) are mood-only and must never appear clickable-as-function.

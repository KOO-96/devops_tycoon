# Visual State Data Source Matrix (FE-ART-002)

- Owner: Program · Status: **FE-ART-002: REVIEW_PENDING**
- Base: dev `65adf13`. Documentation only — no product code, no Frontend-invented
  thresholds.

Purpose: pin every visual state to an **authoritative runtime data source** so a
Frontend implementer never guesses and never computes an operational status the
Backend didn't report. Field / event / incident names below are verified against
the actual code (`simulation/`, `backend/`, `frontend/src/game/nodeStatus.ts`),
not prose.

## Source classes

| Class | Meaning |
|---|---|
| `SNAPSHOT_DIRECT` | a literal field in the snapshot node |
| `HEALTH_ENUM` | the Backend-provided `health` value (Healthy/Warning/Critical/Down) |
| `ENABLED_FIELD` | the node `enabled` boolean |
| `EVENT_DERIVED` | an explicit `DomainEventType` from the event stream |
| `INCIDENT_DERIVED` | an explicit `IncidentType` / `reason_code` |
| `CAPABILITY_DERIVED` | per-kind health applicability (see §Capability) |
| `BACKEND_EXTENSION_REQUIRED` | not representable from current data |
| `DEFERRED` | out of Visual MVP / PR C scope |

A Frontend calculation or on-screen estimate is **not** an accepted source.

## Authoritative enums (verified in code)

- **Health** (`Health`): `Healthy`, `Warning`, `Critical`, `Down` — the ONLY basis
  for Healthy/Warning/Critical/Down.
- **IncidentType** (`simulation/incidents/models.py`): `LB_IMBALANCE`,
  `APP_CPU_OVERLOAD`, `APP_MEM_SATURATION`, `DB_CONNECTION_POOL_EXHAUSTION`,
  `DB_CPU_SATURATION`, `CACHE_MISS_SPIKE`, `REQUEST_TIMEOUT`, `NO_HEALTHY_SERVER`.
- **IncidentPhase**: `WARNING`, `ACTIVE`, `RECOVERING`, `RECOVERED`.
- **DomainEventType** (`simulation/events.py`): REQUEST_CREATED/ROUTED/COMPLETED/
  TIMEOUT/DROPPED/FAILED, CACHE_HIT/MISS/WRITE/EVICTION, CONNECTION_ACQUIRED,
  CONNECTION_POOL_EXHAUSTED, NODE_OVERLOADED/RECOVERED/DOWN, INCIDENT_OPENED/
  PHASE_CHANGED/RESOLVED, COMMAND_APPLIED/REJECTED.
- **Command reject `reason_code`** (`simulation/commands.py`): duplicate_command_id,
  already_applied, command_out_of_order, unknown_command_type,
  invalid_or_duplicate_node_id, unknown_node_kind, node_not_found, missing_node,
  connection_not_allowed, already_connected, not_connected, lb_not_found,
  invalid_algorithm, server_not_found, cache_not_found, db_not_found,
  missing_target_version, invalid_speed. (These describe a **command result**, not a
  node's health.)

> Transport note: the summary the board reads exposes incidents as
> `active_incidents: [{type, target, phase}]`. Raw `DomainEvent`s arrive via the
> WebSocket / events API, not the snapshot — so any EVENT_DERIVED visual is a
> stream-consumption feature, flagged accordingly below.

## Node-kind health capability (runtime literals)

| Node kind | Health capability | Snapshot `health` expected | Missing behavior |
|---|---|---|---|
| `load_balancer` | not applicable | No | `Health N/A` (not_applicable) |
| `app_server` | reported | Yes | `Status unavailable` (not_reported) |
| `redis` | reported | Yes | `Status unavailable` (not_reported) |
| `postgresql` | reported | Yes | `Status unavailable` (not_reported) |

`CAPABILITY_DERIVED`. Backend applicability marker → **BACK-FU-009 (Proposed)**.

## Core status matrix

| Visual state | Applicable kinds | Source class | Exact source | Derivation rule | Fallback | Phase | Decision |
|---|---|---|---|---|---|---|---|
| Healthy | app/redis/postgresql | HEALTH_ENUM | node `health` == `Healthy` | present + equals Healthy | — | Confirmed | Confirmed |
| Warning | app/redis/postgresql | HEALTH_ENUM | node `health` == `Warning` | present + equals Warning | — | Confirmed | Confirmed |
| Critical | app/redis/postgresql | HEALTH_ENUM | node `health` == `Critical` | present + equals Critical | — | Confirmed | Confirmed |
| Down | app/redis/postgresql | HEALTH_ENUM | node `health` == `Down` | present + equals Down | — | Confirmed | Confirmed |
| Disabled | all | ENABLED_FIELD | node `enabled` == false | precedence over health; raw health retained | — | Confirmed | Confirmed |
| Health N/A | load_balancer | CAPABILITY_DERIVED | capability = not applicable + `health` absent | kind has no health concept | — | Confirmed | Confirmed |
| Status unavailable | app/redis/postgresql | CAPABILITY_DERIVED | capability = reported + `health` absent/unknown | health-capable but missing or unrecognized value | — | Confirmed | Confirmed |
| Unknown node kind | (unrecognized) | CAPABILITY_DERIVED | kind ∉ known set | render generated fallback building | universal fallback | Confirmed | Confirmed |
| Selected | all | (Frontend UI) | store `selectedNodeId` | UI-only, independent of health | — | Confirmed | Confirmed (UI) |
| Unselected | all | (Frontend UI) | store `selectedNodeId` | default | — | Confirmed | Confirmed (UI) |
| Reconnecting | (session) | (connection store) | WS socketStatus connecting/reconnecting | connection UI, not node health | — | Confirmed | Confirmed (UI) |
| Snapshot sync failed | (session) | (sync state) | `snapshotSyncState==failed` | post-command refetch failed | Refresh CTA | Confirmed | Confirmed (UI) |
| Asset unavailable | all | (asset load state) | AssetManager fallback resolve | asset missing/failed → fallback | generated fallback | Confirmed | Confirmed |
| Render fallback | all | (asset/kind) | unknown kind or missing texture | generated fallback texture | universal fallback | Confirmed | Confirmed |

**Rules (Confirmed):** Healthy/Warning/Critical/Down come ONLY from an explicit
`health` value — never synthesized from a missing value. Disabled is
`enabled=false` and is distinct from Down. Health N/A ≠ a healthy state. Status
unavailable is never estimated up/down to Healthy/Warning/Critical. Selected/
Reconnecting/Sync-failed are UI/session states, separate from operational health.

## Incident & pressure states

Incidents are surfaced from `active_incidents` (`type`,`target`,`phase`) and are
shown as an overlay/badge on the target node — **independent of the node's health
badge**. A missing health stays N/A / unavailable even when an incident is active;
an incident is never converted into a `health=Critical`.

| Visual state | Real name | Source class | Exact source | Phase | Decision |
|---|---|---|---|---|---|
| LB imbalance | `LB_IMBALANCE` | INCIDENT_DERIVED | IncidentType | Confirmed | Confirmed (incident overlay) |
| No healthy server | `NO_HEALTHY_SERVER` | INCIDENT_DERIVED | IncidentType | Confirmed | Confirmed (incident overlay) |
| CPU pressure (app) | `APP_CPU_OVERLOAD` | INCIDENT_DERIVED | IncidentType | Confirmed | Confirmed (incident, NOT a FE threshold) |
| Memory pressure (app) | `APP_MEM_SATURATION` | INCIDENT_DERIVED | IncidentType | Confirmed | Confirmed (incident) |
| Pool pressure (db) | `DB_CONNECTION_POOL_EXHAUSTION` | INCIDENT_DERIVED | IncidentType | Confirmed | Confirmed (incident) |
| CPU pressure (db) | `DB_CPU_SATURATION` | INCIDENT_DERIVED | IncidentType | Confirmed | Confirmed (incident) |
| Cache-miss spike | `CACHE_MISS_SPIKE` | INCIDENT_DERIVED | IncidentType | Confirmed | Confirmed (incident) |
| Request timeout (incident) | `REQUEST_TIMEOUT` | INCIDENT_DERIVED | IncidentType | Confirmed | Confirmed (incident) |
| Cache miss (single) | `CACHE_MISS` | EVENT_DERIVED | DomainEventType (WS stream) | PR C+ | Conditional (needs event-stream consumption) |
| Cache eviction | `CACHE_EVICTION` | EVENT_DERIVED | DomainEventType (WS stream) | PR C+ | Conditional |
| Connection pool exhausted (event) | `CONNECTION_POOL_EXHAUSTED` | EVENT_DERIVED | DomainEventType (WS stream) | PR C+ | Conditional |
| Node overloaded | `NODE_OVERLOADED` | EVENT_DERIVED | DomainEventType (WS stream) | PR C+ | Conditional |
| Node down (transient) | `NODE_DOWN` / `NODE_RECOVERED` | EVENT_DERIVED | DomainEventType (WS stream) | PR C+ | Conditional (health `Down` already covers persistent) |
| Deploying | (n/a) | BACKEND_EXTENSION_REQUIRED | no snapshot field / no transient event | — | Deferred — needs backend deploy-state |
| Deployment failed | (n/a) | BACKEND_EXTENSION_REQUIRED | no contract signal | — | Deferred |
| Rollback (in progress) | (n/a) | BACKEND_EXTENSION_REQUIRED | only `COMMAND_APPLIED` for ROLLBACK exists (fact, not stage) | — | Deferred |
| Queue pressure | (n/a) | BACKEND_EXTENSION_REQUIRED | `queue_length`/`queue_capacity` exist but no reported severity | — | Deferred (no FE threshold) |
| Capacity pressure (cache) | (n/a) | BACKEND_EXTENSION_REQUIRED | `used_entries`/`capacity_entries` exist; severity only via CACHE_MISS_SPIKE incident | — | Deferred (no FE threshold) |

**Threshold policy (Confirmed):** raw metrics (`cpu_usage`, `mem_usage`,
`queue_length`/`queue_capacity`, `active_connections`/`waiting_connections`/
`max_connections`, `used_entries`/`capacity_entries`, `hit_rate`) may be **displayed
as numbers** (SNAPSHOT_DIRECT) but the Frontend must NOT derive Warning/Critical/
"pressure" from them. Severity is already the Backend's job via `health` and the
IncidentTypes above.

## Request-flow states

Base request flow is an **aggregate** visualization, not per-request replay.

| Flow representation | Source class | Decision |
|---|---|---|
| Pulses driven by observed REQUEST_* events (aggregate rate) | EVENT_DERIVED | Conditional (PR D; needs event-stream consumption) |
| Idle / no-traffic (no events) | EVENT_DERIVED | Conditional |
| Decorative looping "activity" with no event basis | (none) | Deferred (decorative only; must not imply real traffic) |
| Fake per-request markers | (none) | **Prohibited** — never shown as real requests |

Flow colour must not assert a success/failure **cause**; only aggregate direction/
rate. Precise volume mapping = **UI-D-011 (Proposed)**.

## PR C confirmed vs deferred (summary)

- **Confirmed for PR C:** Healthy, Warning, Critical, Down, Disabled, Health N/A,
  Status unavailable, Unknown-kind fallback, Selected, Incident badge/overlay
  (all 8 IncidentTypes via `active_incidents`), Missing-asset fallback.
- **Conditional (only with the named event/payload actually consumed):** single
  CACHE_MISS/EVICTION/POOL_EXHAUSTED/NODE_OVERLOADED/NODE_DOWN transient effects,
  aggregate request flow.
- **Deferred / Backend-extension:** Deploying, Deployment-failed, Rollback stages,
  queue/capacity/pool/cpu/mem "pressure" as node sub-states derived by the client.

## FE-ART-002 completion criteria

FE-ART-002 becomes a completion candidate ONLY when: every PR C state has a real
data source; exact field/enum/event/incident names are verified (done here);
no Frontend-invented thresholds; health ≠ incident; not_applicable ≠ not_reported;
Backend/Frontend responsibility is explicit; unsupported states are Deferred or
Backend-extension; and Backend + Frontend + Program + DevCTO have reviewed.

**Current status: FE-ART-002 = REVIEW_PENDING.** Linked: BACK-FU-009 (Proposed),
UI-D-011 (Proposed request-flow volume), FE-ART-003 (texture lifecycle, separate).

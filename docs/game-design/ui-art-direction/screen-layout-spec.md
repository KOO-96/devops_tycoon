# Screen Layout Spec

- Owner: Program · Status: layout = Proposed; data availability = Confirmed against Backend contract

Information frame (re-designed from the reference mood, not copied):

```
┌───────────────────────────────────────────────────────────────┐
│ TOP HEADER: Logo · Session · Cash · Revenue · Trust · Tick ·  │
│             Speed/Pause · Backend · WS · Incidents(n)          │
├─────────┬───────────────────────────────────────┬─────────────┤
│ LEFT    │                                       │ RIGHT       │
│ NAV     │        ISOMETRIC CAMPUS BOARD         │ CONTEXT     │
│ (vert.) │        (Pixi canvas)                  │ PANEL       │
│         │                                       │             │
├─────────┴───────────────────────────────────────┴─────────────┤
│ OPTIONAL BOTTOM: selection / command bar (Proposed)           │
└───────────────────────────────────────────────────────────────┘
```

## Top HUD — MVP fields (data exists in Backend summary/contract → Confirmed available)

`Cash`, `Revenue`, `Trust (user_trust)`, `Current Tick`, `Pause state`, `Speed 1×/2×/4×`,
`Backend connection`, `WebSocket connection`, `Active Incident count`. All are present in
the session summary or connection store today.

**Future Slots (design placeholder only, not active):** company Level, Score, campaign
stage, promotion gauge, investor rank, Black Friday progress → render as an empty/greyed
"coming later" slot or hide entirely (UI-D-005). Never show a live value.

## Left Nav — items + MVP status

| Item | Purpose | MVP status |
|---|---|---|
| Campus / Overview | default board view | MVP Active |
| Build | add/remove nodes (ADD_NODE/REMOVE_NODE) | MVP Active |
| Connect | connect/disconnect (CONNECT/DISCONNECT) | MVP Active |
| Deploy | deploy/rollback on an app server | MVP Active (acts on selected App) |
| Monitor | metrics/observability view | MVP Read-only (uses snapshot metrics) |
| Research | R&D tree | Disabled / Coming Later |

Disabled/Coming-later items must look inactive (not a working button). Final item set =
**UI-D-004**.

## Right Context Panel — MVP

`Active Incident` list · `Selected Node` detail · `Node Metrics` (cpu/mem/queue/pool from
snapshot) · `Connection` state · `Recent Events` · `Snapshot Sync` state. Current
Task/Mission panel is **Deferred** (needs campaign + event scheduler). Final MVP set =
**UI-D-005**.

## Per-screen specs

### Start Page
- Fresh game logo (new, not the reference logo).
- New-game CTA; Seed + initial user count inputs (both exist in create contract).
- A "development Foundation" note; state that authentication is not implemented and the
  session id is not a security boundary (already surfaced in the current StartPage).
- Background art: bright campus vista (Proposed).

### Game Page — Normal
- Campus board (Pixi), top HUD, left nav, right context panel, accessible NodeList, connection
  banner, selected-node detail, command UI. Board and NodeList share one data source (the
  snapshot).

### Game Page — Incident
- Affected node highlighted on the board (icon + motion + outline, not colour alone).
- Right alert panel lists active incidents (type/target/phase from backend).
- Warning vs Critical clearly differentiated; healthy vs problem nodes contrast.
- Never reads as a forced game-over; the game keeps running.

### Loading
- Never show an empty "normal" board. Show a campus-loading / data-sync state (maps to
  `loadState = loading`).

### Session Not Found (`not_found`)
- No board. "게임 세션을 찾을 수 없습니다." + shortened session id + New-game CTA +
  back-to-Start CTA + request_id if present. No infinite retry. (Implemented today.)

### Recoverable Error (`recoverable_error`)
- "일시적으로 연결할 수 없습니다" tone (do not claim the session was deleted) + Retry (re-runs
  bootstrap) + back-to-Start + request_id. (Implemented today.)

### Fatal Error (`fatal_error`)
- Snapshot-version/compatibility message; no empty board; no auto-retry loop; back-to-Start.
  Advanced migration UX Deferred (FE-FU-006). (Implemented today.)

### Snapshot Sync Failed
- Banner: command may have been applied; offer "Refresh board" (re-fetch snapshot only); do
  not invite re-running the command. (Implemented today via SnapshotSyncBanner.)

## Responsive / small screen (Proposed → UI-D-013)
Base design 1440×810; min 1280×720 (desktop-first). Below that: collapse left nav to
icons+labels, right panel to a toggle drawer, keep top HUD core fields. Full mobile is
Deferred.

# UI State Matrix

- Owner: Program · Status: node-state set = Confirmed (from contract); visual cues = Proposed

Every status uses **at least two non-colour cues** (icon + motion/pattern + text) so it is
legible for colour-blind users, on small/low-res screens, in screenshots, and in the
canvas-alternative NodeList (Confirmed accessibility principle).

## Health states (Confirmed set: Healthy / Warning / Critical / Down)

| State | Colour (Proposed) | Icon | Motion / pattern | Text |
|---|---|---|---|---|
| Healthy | green | check / signal | steady soft blink | Healthy |
| Warning | amber/orange | ! | slow pulse | Warning |
| Critical | red | !! | fast pulse / shake | Critical |
| Down | grey/purple | ✕ | smoke / stopped / dimmed | Down |
| Deploying | blue | arrow / box | progress sweep | Deploying |
| Disabled | slate | pause / lock | reduced saturation, static | Disabled |

Deploying/Disabled are UI states derived from commands/enabled flag, not part of the core
4-level health enum.

## Health applicability — not_applicable / not_reported (Confirmed policy)

`health` is optional in the snapshot; a missing value is **never** shown as Healthy.
The single resolver (`game/nodeStatus.ts`) maps it by node-kind capability:

| Situation | State | Colour (neutral) | Glyph | Text |
|---|---|---|---|---|
| kind has no health concept (load_balancer) | not_applicable | blue-grey (not green) | `—` | Health N/A |
| health-capable kind but value missing (app/redis/db) | not_reported | grey (not green) | `?` | Status unavailable |

Neutral states never reuse Healthy/Warning/Critical/Down colours, always carry a
non-colour glyph + text, and are distinguished for screen readers ("health status
not applicable" vs "…unavailable"). Missing health is never auto-promoted to
Warning/Critical. Incidents are shown separately from health (an LB with
`not_applicable` health can still show LB_IMBALANCE / NO_HEALTHY_SERVER).

Backend applicability marker = **BACK-FU-009** (Proposed). FE-ART-002 (full
state-data-source matrix) remains not complete.

## Per-node-kind state variants (Confirmed states; art Proposed)

- **Load Balancer:** Healthy · Imbalanced · No-Healthy-Server · Down.
- **App Server:** Healthy · CPU Warning · CPU Critical · Memory Warning · Deploying ·
  Disabled · Down.
- **Redis:** Healthy · Cache-Miss Warning · Capacity Warning · Eviction · Disabled · Down.
- **PostgreSQL:** Healthy · Pool Warning · Pool Critical · CPU Warning · Down.

These map to snapshot fields (`health`, `enabled`, `cpu_usage`, `mem_usage`, `queue_*`,
`max_connections`) already present. The badge shows the **health** enum; kind-specific
sub-warnings (e.g. "Pool Critical") are secondary annotations.

## Connection states (Proposed)

| State | Cue |
|---|---|
| Active connection | solid line + animated flow pulses in traffic direction |
| Idle/no traffic | solid line, no pulses |
| Removed (DISCONNECT) | line disappears immediately (snapshot re-fetch) |
| Isolated node | no lines; node rendered slightly separated / greyed base |
| Invalid attempt | rejected by backend → COMMAND_REJECTED banner (no line drawn) |

## Load / error screen states (Confirmed — implemented)

| loadState | Screen |
|---|---|
| loading | campus-loading / sync indicator, never a blank normal board |
| ready | full board |
| not_found | not-found recovery screen + CTAs |
| recoverable_error | temporary-outage screen + Retry |
| fatal_error | incompatibility screen, no auto-retry |
| (snapshotSyncState=failed) | SnapshotSyncBanner + Refresh board |

## Selection & incident overlays (Proposed)

- Selection: distinct ring/outline (cyan/blue) + the node is echoed in the right panel; a
  removed selected node clears selection (already implemented).
- Incident target: a persistent alert marker above the node + entry in the right alert
  panel; Warning vs Critical differ by icon + motion intensity, not colour alone.

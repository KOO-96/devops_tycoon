# Visual Implementation Roadmap

- Owner: Program (plan) / Frontend (impl) · Status: Proposed

Extends the existing Frontend Foundation (do **not** rewrite it). Each PR is small,
reviewable, and keeps all Foundation tests green.

## Current Frontend → future role (Confirmed components; treatment Proposed)

| Current component | Future visual role | Keep / extend / replace | Why |
|---|---|---|---|
| `GameCanvas.tsx` | campus render container | **Keep** | lifecycle already correct |
| `game/pixi/createGameScene.ts` (GameScene) | tile/building/connection/effect layers | **Extend** | add layers + sprites onto the existing world/edge/node layers |
| `game/pixi/isometric.ts` | iso transforms + layout | **Extend** | keep 128×64 logical / 64×32 source (UI-D-002); add footprints |
| `game/pixi/nodes.ts` | node→visual mapping | **Extend** | swap glyph placeholders for building sprites |
| `components/common/NodeList.tsx` | accessibility + management panel | **Keep** | canvas-alternative, stays authoritative |
| `components/hud/Hud.tsx` | top info bar | **Extend** | add Future Slots (inactive), styling |
| `components/hud/ControlBar.tsx` | speed/pause + command entry | **Keep/extend** | |
| `components/incidents/IncidentPanel.tsx` | right alert card | **Extend** | styling + target link |
| `components/common/SessionErrorScreen.tsx` | full-screen state panels | **Keep** | already covers not_found/recoverable/fatal |
| `components/common/SnapshotSyncBanner.tsx` | sync-failure recovery | **Keep** | |
| `state/*` (Zustand) | UI state | **Keep** | no Pixi objects stored in state (Confirmed) |

## PR A — Visual tokens & layout shell — DELIVERED (agent/frontend)

Implemented: design tokens (`src/styles/`), CSS-grid `GameLayout` (header/nav/
campus/context/command), left nav with correct enabled/disabled states, styled
loading/recovery/sync screens, responsive 1440×810→1280×720, accessibility
(landmarks, skip link, aria-current/disabled, reduced-motion), Pixi/REST/WS
behavior preserved. See `docs/architecture/frontend-layout-shell.md`. Original
scope below:
- **Scope:** design tokens (palette/spacing/typography vars), overall grid layout, top HUD
  frame, left nav (with correct enabled/disabled states), right panel frame, error-screen
  styling.
- **Not in scope:** iso building art, effects.
- **Assets:** nav/status icons (or placeholders), fonts (candidates only).
- **Tests:** layout renders per loadState; nav disabled items non-interactive; a11y roles.
- **Perf risk:** low. **Reviewers:** Program, Frontend.

## PR B — Isometric tile & building system — DELIVERED (agent/frontend)

Implemented: explicit scene layers, 1×1–4×4 footprints, stable depth sorting,
anchor/pivot rules, BuildingView + node adapter (unknown-kind safe), Asset Manager
+ manifest + generated fallback, connection/selection views, diff sync (50-node
verified) — on the unchanged 128×64 grid. FE-ART-002/003 + ASSET-OPS-001/002 remain
PR C gates. See `docs/architecture/frontend-isometric-building-system.md`. Original
scope below:
- **Scope:** tile grid render, camera (pan clamp, keyboard pan), layer split, building
  sprite placement (anchor/footprint), selection bounds.
- **Assets:** ground/terrain tiles, one placeholder building.
- **Tests:** grid↔screen, selection hit-area, single canvas, teardown cleanup.
- **Perf risk:** medium (layer count). **Reviewers:** Frontend, Ops.

## PR C — Functional node visuals — COMPLETE_IN_DEV
- **Status: COMPLETE_IN_DEV** (asset runtime, handles/versioned cache, Entry→Category→
  Universal fallback, checksum integrity refetch, incident overlay, client source
  classes, generation-safe session bootstrap; Ops live-browser VERIFIED). Merged to
  `dev` via PR #21 → review/devcto and PR #22 → dev. Development placeholder assets
  only — **no final sprites/atlases**; EVENT_DERIVED effects and first-production-asset
  gates remain open.
- **Prerequisite policies (DevCTO APPROVED_WITH_FOLLOW_UP, on dev):** FE-ART-002,
  FE-ART-003, ASSET-OPS-001/002 + Manifest Baseline. Start/Completion/First-Production-Asset
  gates and POLICY-C-FU-001…010 are indexed in
  [`visual-pr-c-policy-gates.md`](./visual-pr-c-policy-gates.md).
- **Scope:** the 4 building kinds + state variants + connection lines (add/remove) driven by
  the snapshot.
- **Assets:** building atlases (all health/kind states).
- **Tests:** snapshot→board sync for all 14 commands; Down≠Healthy; disconnect removes line.
- **Perf risk:** medium. **Reviewers:** Frontend, Program, Ops.

## PR D — Effects & feedback
- **Scope:** request flow, connection flow, alert overlay, deploy/rollback, down, cache
  hit/miss, DB pool pressure.
- **Assets:** effect atlases.
- **Tests:** effect starts/stops on events; particle/animation caps; reduced-motion honored.
- **Perf risk:** high (particles) → enforce caps. **Reviewers:** Ops, Frontend.

## PR E — Characters & environment (Phase 2)
- **Scope:** decorative staff, vehicles, environment decoration, campus liveliness.
- **Assets:** character + decoration atlases.
- **Tests:** decorative objects non-interactive; off-screen culling; perf at 50+ nodes.
- **Perf risk:** high. **Reviewers:** Program, Ops.

## Sequencing
A → B → C are the **Visual MVP** (playable, legible board). D completes MVP feedback. E is
Phase 2. Campaign/Black-Friday/investor/AI-CTO visuals are Phase 3 (separate direction).

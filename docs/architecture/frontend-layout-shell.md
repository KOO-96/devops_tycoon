# Frontend Layout Shell (Visual PR A)

- Version: v0.1.0 · Status: Draft (for review/devcto)
- Implements the Visual MVP layout shell for the Illustrated Pixel Hybrid direction
  (UI-D-001) without changing Pixi/coordinate/asset systems (UI-D-002).

## React DOM ↔ Pixi boundary

React DOM owns: top HUD, left navigation, right context panel, command bar,
loading/error/recovery screens, and the accessible NodeList. PixiJS owns only the
campus canvas (`GameCanvas`/`GameScene`, unchanged). DOM panels are laid out via
CSS Grid — never absolutely positioned over the canvas — so canvas pointer input
is never blocked; campus overlays (reconnecting / dropped / empty) use
`pointer-events: none`.

## Design tokens

`frontend/src/styles/tokens.css` (CSS custom properties): color (sky/ground/
surfaces/borders/text/interactive/reserved status), typography (system stacks;
**no external fonts in PR A**), spacing (4px scale), shape, shadow, z-index,
motion (with `prefers-reduced-motion` overrides). Values are the art-direction
**Proposed** palette — not promoted to Confirmed without Program approval. Loaded
in `main.tsx`: tokens → reset → global → utilities.

## Layout structure

`components/layout/`: `AppShell` (bright background), `GameLayout` (CSS-grid
`header / nav | main | aside / command`), `TopHud` (brand + `Hud` + connection),
`LeftNavigation`, `CampusFrame` (`<main>`, campus title + status strip +
`GameCanvas` + overlays), `ContextPanel` (`<aside>`), `CommandBar`. UI primitives
in `components/ui/`: `Panel`, `SectionHeader`, `EmptyState`, `StatusBadge`,
`MetricDisplay`, `PixelButton`. Existing HUD/NodeList/Incident/Event/Inspector
components are **reused unchanged** inside these layout wrappers.

## Landmarks & accessibility

`header` (banner) · `nav` (Campus sections) · `main#campus-main` (campus) ·
`aside` (Context panel), plus a "Skip to campus" link. Left-nav uses
`aria-current="page"` for selection and `aria-disabled` for Research (Coming
Later). Status uses colour **+** icon **+** text (StatusBadge / status classes).
Errors use `role="alert"`/`aria-live`; loading uses `role="status"`. Reduced-motion
zeroes transition/pulse tokens. The NodeList remains the canvas-alternative
keyboard/screen-reader path.

## Responsive

Base 1440×810; usable to 1280×720 (nav tag hidden ≤1360px; nav collapses to icons
≤1180px; context panel width clamps; campus keeps a usable area). Full mobile is
Deferred. Resize uses the existing Pixi `renderer.resize` — the Application is
**not** re-created on React re-render or viewport change (verified: one canvas).

## Command placement decision (§15)

Global commands (Pause / Speed via the existing `ControlBar`) live in the bottom
**CommandBar**; node-specific commands stay in the right-panel `NodeInspector`.
Commands are never duplicated across the nav and the command bar.

## Left navigation shell (§12)

Selection + panel-switch shell only — no fake backend. All MVP-active items
currently focus the same campus view; real per-item views are a later PR. Research
is disabled.

## Explicitly out of scope in PR A

Final sprites/logo/fonts, texture atlas, Asset Manager, footprint/anchor/depth
changes, Pixi coordinate changes, connection/request-flow visual systems,
per-state building variants, and any Backend/Simulation/contract change. Sprite
positions use CSS/geometry placeholders (the campus keeps the current Pixi
diamond renderer).

## PR B entry conditions

After this shell reaches dev: PR B adds the isometric tile + building system
(keeping 128×64), footprint/anchor/layer/depth, an Asset Manager skeleton, and a
fallback asset — reusing this shell's regions and tokens.

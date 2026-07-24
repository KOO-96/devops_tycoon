# Decisions Required — UI-D-001…015

Each decision: options · recommendation · rationale · impact · status · owner.
Status legend: Confirmed / Proposed / TBD / Deferred.

Reference reviewed by Program; the reference genre is **Illustrated Pixel Hybrid** and the
core visual decisions below are now **Confirmed**. Only **UI-D-014** (asset production
method) remains Proposed.

---

### UI-D-001 — Final visual genre
- Options: (a) pure low-res Pixel Art, (b) **Illustrated Pixel Hybrid**, (c) flat vector.
- Decision: **(b) Illustrated Pixel Hybrid.**
- Definition: buildings + environment are pixel-styled **illustration** (pixel outline/
  texture, higher-detail than classic low-res dots); UI panels + body text are crisp,
  normal UI; not everything is constrained to coarse dots; keep pixel texture/outline and
  integer-scaling rules; long Korean body text does not use a pixel font.
- Rationale: matches the reviewed reference; strong silhouettes with detailed buildings while
  keeping panels legible.
- Impact: all assets, palette, fonts, pipeline.
- Status: **Confirmed.** Owner: Program.

### UI-D-002 — Isometric tile size
- Decision: keep the current Foundation grid.
  - Logical isometric tile: **128×64**
  - Source art module: **64×32**
  - Export scale: **2× integer scaling**
  - Texture filtering: **nearest-neighbor**
- Do **not** change the Frontend coordinate system to a 64×32 logical tile.
- Rationale: preserves the current GameScene + coordinate transforms (no Foundation rework);
  ensures functional-building legibility at 1440×810; suits the reference's detailed
  buildings; 64×32 source module keeps pixel consistency.
- Impact: isometric transforms (unchanged), building art authored at 64×32 → shown at 128×64.
- Status: **Confirmed.** Owner: Program + Frontend.

### UI-D-003 — Base / min resolution
- Decision: base **1440×810**, min **1280×720**, desktop-first.
- Impact: layout breakpoints, camera.
- Status: **Confirmed.** Owner: Program.

### UI-D-004 — Left nav final items
- Decision: Campus/Overview · Build · Connect · Deploy · Monitor · **Research (Disabled /
  Coming Later)**. Do not copy the reference's Develop/Integrate labels.
- Recommendation: MVP-active {Campus, Build, Connect, Deploy}, read-only {Monitor},
  disabled {Research}.
- Impact: nav component, enabled/disabled visuals.
- Status: **Confirmed** (item set); active/read-only tiering **Proposed**. Owner: Program.

### UI-D-005 — Right panel MVP composition
- Decision: Active Incidents · Selected Node · Node Metrics · Connections · Recent Events ·
  Snapshot Sync. Current Task / Mission hidden until campaigns exist.
- Impact: right panel component.
- Status: **Confirmed** (MVP set); card styling **Proposed**. Owner: Program.

### UI-D-006 — Characters in MVP?
- Decision: **Characters are excluded from the Visual MVP; they are a Phase 2 decorative
  element.**
- Impact: MVP asset scope, perf.
- Status: **Confirmed.** Owner: Program.

### UI-D-007 — Pixel font scope + CJK
- Decision: Pixel font for **logo / large signage / short numeric labels**; **legible Sans
  for Korean body + HUD text**; **monospace for Node IDs / technical info**.
- Rationale: pixel fonts hurt long-text/CJK legibility; UI mixes KO/EN.
- Impact: typography; font licensing review (no font files committed).
- Status: **Confirmed** (role policy); specific font files/licenses **Proposed** (still to be
  selected under this policy). Owner: Program.

### UI-D-008 — Are campus zones a hard constraint?
- Decision: Campus zones are a **soft guide** for the tutorial and readability; they do
  **not** force real node placement.
- Rationale: keeps deterministic `layoutGrid` valid; Backend has no spatial model.
- Impact: layout algorithm, tutorial.
- Status: **Confirmed.** Owner: Program.

### UI-D-009 — Functional node ↔ facility building relationship
- Decision: **1 node ↔ 1 functional building**; facilities/zones are decorative grouping only.
- Rationale: preserves "board = real topology".
- Impact: mapping, selection, hit areas.
- Status: **Confirmed.** Owner: Program + DevCTO.

### UI-D-010 — Building tier visualization
- Decision: **Visual Phase 2** (footprint + add-on modules); none in MVP.
- Impact: art volume.
- Status: **Deferred.** Owner: Program.

### UI-D-011 — Request-flow representation
- Recommendation: light-pulse packets along connections, sampled/approximate, rate scales
  with SET_SPEED (client computes no ticks).
- Impact: effects, perf.
- Status: **Proposed.** Owner: Program + Frontend.

### UI-D-012 — Per-state animation intensity + reduced motion
- Recommendation: intensity per state (ui-state-matrix); support a reduced-motion setting
  that drops to static + icon/text cues.
- Impact: animation specs, accessibility.
- Status: **Proposed.** Owner: Program + Ops.

### UI-D-013 — Mobile / small-screen strategy
- Recommendation: desktop-first with responsive collapse at min res; full mobile Deferred.
- Impact: layout, testing.
- Status: **Proposed.** Owner: Program.

### UI-D-014 — Asset production method
- Options: hand-pixeled, tool-assisted, commissioned, or AI-generated.
- Recommendation / policy:
  - AI or illustration tools **may** be used for **concept** work.
  - Final game assets are normalized to DevOps Tycoon's own design.
  - **No reproduction** of the reference's buildings / characters / icons.
  - Raw generated images are **not** used directly as sprites.
  - Post-process to the tile / anchor / palette / outline / atlas specs.
  - Ship only assets with verified rights / licensing.
- Impact: pipeline, licensing, timeline.
- Status: **Proposed.** Owner: Program + DevCTO.

### UI-D-015 — Reference image storage + rights
- Decision: reference images are **not committed** to the repo; only the textual analysis and
  decision rationale are kept; do not reproduce the original logo / buildings / characters /
  icons.
- Impact: repo hygiene, licensing.
- Status: **Confirmed.** Owner: Program.

---

## Blocking vs non-blocking
The genre (UI-D-001) and tile size (UI-D-002) are now **Confirmed**, so implementation
**PR A / PR B** are unblocked. Remaining open items are non-blocking tuning: UI-D-011,
UI-D-012, UI-D-013 (Proposed), UI-D-014 (asset-production method, Proposed), and the
concrete font-file selection under the Confirmed UI-D-007 policy.

# Decisions Required — UI-D-001…015

Each decision: options · recommendation · rationale · impact · status · owner.
Status legend: Confirmed / Proposed / TBD / Deferred.

---

### UI-D-001 — Final visual genre
- Options: (a) Pixel Art, (b) Illustrated / pixel-hybrid, (c) flat vector.
- Recommendation: **(a) Pixel Art, 2.5D isometric.**
- Rationale: matches the reference mood; strong per-building silhouettes; cheap to animate.
- Impact: all assets, palette, fonts, pipeline.
- Status: **TBD** (gated on viewing the actual reference — see UI-D-015). Owner: Program → DevCTO.

### UI-D-002 — Isometric tile size
- Options: 64×32 (proposed) vs 128×64 (current Foundation `DEFAULT_TILE`).
- Recommendation: **64×32 logical + 2× integer display scale** (validate legibility) OR keep
  128×64 if sprite detail needs it.
- Rationale: 64×32 is a classic crisp pixel scale; 128×64 is already wired.
- Impact: isometric transforms, all building art dimensions, PR B.
- Status: **TBD.** Owner: Program + Frontend.

### UI-D-003 — Base / min resolution
- Options: base 1440×810, min 1280×720 (proposed); alternatives 1280×720 / 1024×576.
- Recommendation: **base 1440×810, min 1280×720, desktop-first.**
- Impact: layout breakpoints, camera.
- Status: **Proposed.** Owner: Program.

### UI-D-004 — Left nav final items
- Options: {Campus, Build, Connect, Deploy, Monitor, Research} vs a reduced MVP set.
- Recommendation: MVP-active {Campus, Build, Connect, Deploy}, read-only {Monitor},
  disabled {Research}.
- Impact: nav component, enabled/disabled visuals.
- Status: **Proposed.** Owner: Program.

### UI-D-005 — Right panel MVP composition
- Options: which cards ship in MVP.
- Recommendation: Active Incident · Selected Node · Node Metrics · Connection · Recent
  Events · Snapshot Sync. (Current Task/Mission **Deferred**.)
- Impact: right panel component.
- Status: **Proposed.** Owner: Program.

### UI-D-006 — Characters in MVP?
- Options: include decorative staff in MVP vs Phase 2.
- Recommendation: **Deferred to Phase 2** (decorative only, not needed for legibility).
- Impact: MVP asset scope, perf.
- Status: **Proposed (lean Deferred).** Owner: Program.

### UI-D-007 — Pixel font scope + CJK
- Options: pixel font everywhere vs display-only + legible sans for body/CJK.
- Recommendation: **pixel font for logo/short labels; legible sans for body + Korean.**
- Rationale: pixel fonts hurt long-text/CJK legibility; UI mixes KO/EN today.
- Impact: typography, font licensing review (no font files committed).
- Status: **TBD** (font choice + license). Owner: Program.

### UI-D-008 — Are campus zones a hard constraint?
- Options: hard zone placement vs soft/tutorial-only.
- Recommendation: **soft / tutorial-only** (keeps deterministic `layoutGrid` valid; Backend
  has no spatial model).
- Impact: layout algorithm, tutorial.
- Status: **Proposed.** Owner: Program.

### UI-D-009 — Functional node ↔ facility building relationship
- Options: 1 node = 1 building (proposed) vs node clusters inside a shared facility.
- Recommendation: **1 node ↔ 1 functional building**; facilities/zones are decorative
  grouping only.
- Rationale: preserves the "board = real topology" principle.
- Impact: mapping, selection, hit areas.
- Status: **Proposed (strong).** Owner: Program + DevCTO.

### UI-D-010 — Building tier visualization
- Options: tiers via size/footprint, via add-on modules, or none in MVP.
- Recommendation: **none in MVP**; introduce tiers in Phase 2 (footprint + modules).
- Impact: art volume.
- Status: **Deferred.** Owner: Program.

### UI-D-011 — Request-flow representation
- Options: packets, light pulses, trucks, animated pipes; volume: sampled vs per-request.
- Recommendation: **light-pulse packets along connections, sampled/approximate**, rate
  scales with SET_SPEED (client computes no ticks).
- Impact: effects, perf.
- Status: **Proposed.** Owner: Program + Frontend.

### UI-D-012 — Per-state animation intensity + reduced motion
- Options: intensity levels; reduced-motion support now vs later.
- Recommendation: define intensity per state (see ui-state-matrix); **support a
  reduced-motion setting** that drops to static + icon/text cues.
- Impact: animation specs, accessibility.
- Status: **Proposed.** Owner: Program + Ops.

### UI-D-013 — Mobile / small-screen strategy
- Options: desktop-only MVP vs responsive-collapse vs full mobile.
- Recommendation: **desktop-first with responsive collapse** at min res; full mobile
  Deferred.
- Impact: layout, testing.
- Status: **Proposed.** Owner: Program.

### UI-D-014 — Asset production method
- Options: hand-pixeled, tool-assisted, commissioned, or AI-generated (license/consistency
  risk).
- Recommendation: **TBD** — pick a method that guarantees consistent pixel scale + clear
  licensing; document per-asset provenance.
- Impact: pipeline, licensing, timeline.
- Status: **TBD.** Owner: Program + DevCTO.

### UI-D-015 — Reference image storage + rights
- Options: commit images (if rights cleared) vs text-only analysis (current).
- Recommendation: **text-only** until rights are confirmed; user to attach image(s)/path so
  UI-D-001 can be confirmed against the real reference.
- Impact: UI-D-001 confirmation, repo hygiene.
- Status: **TBD.** Owner: Program + user.

---

## Blocking vs non-blocking
None of these block the **documentation** deliverable. **UI-D-001 (+UI-D-015)** and
**UI-D-002** should be resolved before **PR A / PR B** of the implementation roadmap begin,
since they fix genre and tile size.

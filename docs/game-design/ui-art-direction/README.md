# UI Art Direction (UI-FU-001)

- Owner: Program (UI Art Direction) · Status: Draft for review/devcto
- Base: dev @ `93f0a95` (Simulation + Backend + Frontend Foundation merged)
- Scope: **documentation only** — no product code, no image assets, no PixiJS/React/CSS changes.

This package defines the final visual direction and the information architecture for
DevOps Tycoon so a Frontend engineer can implement the look **without guessing**, and
so Program/DevCTO can lock the remaining decisions before any pixel art is produced.

## Reading order

1. [ui-art-direction-master.md](ui-art-direction-master.md) — mood, world, principles, MVP↔Future split.
2. [screen-layout-spec.md](screen-layout-spec.md) — every screen + information structure.
3. [isometric-campus-spec.md](isometric-campus-spec.md) — grid, zones, layers, z-order.
4. [gameplay-visual-mapping.md](gameplay-visual-mapping.md) — Simulation node ↔ on-screen object mapping.
5. [asset-style-guide.md](asset-style-guide.md) — building catalog, palette, typography, icons.
6. [ui-state-matrix.md](ui-state-matrix.md) — per-state visual language (colour + icon + motion + text).
7. [pixi-asset-pipeline.md](pixi-asset-pipeline.md) — atlas, naming, anchors, lifecycle.
8. [visual-implementation-roadmap.md](visual-implementation-roadmap.md) — PR-by-PR plan (A–E).
9. [decisions-required.md](decisions-required.md) — UI-D-001…015 open decisions.
10. [references/README.md](references/README.md) — reference mood analysis (no committed images).

## Decision status legend

- **Confirmed** — fixed by current game design and the implemented Backend/Simulation/Frontend contracts.
- **Proposed** — a recommended default, adjustable after Frontend prototyping / playtest.
- **TBD** — needs a Program or DevCTO decision (see decisions-required.md).
- **Deferred** — post-MVP.

Nothing in this package is Confirmed on the basis of a reference image (see the note below).

## Reference image note (important)

The reviewing AI author of these documents **could not view the reference image(s)**. All
mood/structure analysis here is derived from the **textual description** supplied in the
task brief. Therefore the final visual genre and any image-derived specifics remain
**Proposed/TBD** (see **UI-D-001** and **UI-D-015**). Before locking the visual genre,
the user should attach the image(s) or provide a local path so the direction can be
confirmed against the actual reference. Reference images are **not** committed to the repo
(unclear usage rights) — only a textual feature analysis is stored.

## Non-goals (this task)

No sprite/logo production, no React/CSS/PixiJS code, no Backend/Simulation/contract
changes, no final character design, no audio, no full Figma mockups, no final mobile UI,
no AI-CTO chat UI.

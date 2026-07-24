# Isometric Campus Spec

- Owner: Program · Status: grid **Confirmed** (UI-D-002/003), aligned with the current PixiJS Foundation; footprints/camera details Proposed

## Logical grid (Confirmed — UI-D-002)

| Parameter | Value | Status |
|---|---|---|
| Logical isometric tile | **128×64** (matches `isometric.ts` DEFAULT_TILE) | Confirmed |
| Source art module | **64×32** | Confirmed |
| Export / display scale | **2× integer scaling** | Confirmed |
| Texture filtering | **nearest-neighbor** | Confirmed |
| Building footprints | 2×2, 3×3, 4×4 tiles | Proposed |
| Base design resolution | 1440×810 (16:9) | Confirmed (UI-D-003) |
| Min resolution | 1280×720 | Confirmed (UI-D-003) |

The Frontend coordinate system is **not** changed: the current Foundation already implements
iso transforms (`gridToScreen`/`screenToGrid`), a deterministic `layoutGrid`, and a pannable
world container with `edgeLayer` + `nodeLayer` at a 128×64 logical tile — all kept as-is.
Artists author sprites at a **64×32 source module** (so pixel density feels right) and the
game renders them at the **128×64** logical tile via **2× integer scaling** with
nearest-neighbor filtering. This keeps the reference's detailed buildings legible at
1440×810 without any Foundation rework.

## Campus zones (Proposed — UI-D-008)

Candidate zones: Traffic, Application, Cache, Data, Deployment (P2), Monitoring (P2),
Research (P2), Expansion Lots. Nodes are **not required** to be locked to a zone (the
Backend imposes no spatial model), but the initial tutorial layout MAY group nodes by zone
to teach the tech relationships. UI-D-008 decides whether zones are a hard constraint
(recommended: **soft/tutorial-only**, so the deterministic `layoutGrid` stays valid).

## Layer / z-order (Confirmed structure, extends current layers)

Bottom → top:
1. Ground / terrain (static, cached)
2. Roads / cables (mostly static)
3. Building base / footprint shadow
4. Building body (functional node sprite)
5. Characters (decorative, Phase 2)
6. Data-flow effects (request/connection pulses)
7. Status icons (per-node health badge)
8. Selection highlight (ring/outline)
9. Alert overlay (incident marker)
10. HUD / DOM (outside the canvas)

Maps onto the existing `world → {edgeLayer, nodeLayer}` container: split into
`terrainLayer < edgeLayer < baseLayer < nodeLayer < characterLayer < effectLayer <
overlayLayer` (extension, not replacement — see visual-implementation-roadmap PR B).

## Sprite placement rules (Proposed)

- **anchor/pivot:** bottom-center of the building footprint sits on the tile's screen
  anchor (so taller buildings grow upward without shifting their base).
- **footprint:** N×N tile diamond; screen position from `gridToScreen(col,row)` of the
  footprint's base tile.
- **z-index within nodeLayer:** sort by `(col+row)` (screen depth) so nearer buildings
  overlap farther ones correctly.
- **selection bounds:** the footprint diamond (not the full sprite rect) to avoid
  overlapping click targets; falls back to sprite bounds if a footprint isn't defined.
- **hit area:** functional buildings only; decorative objects have no hit area.

## Camera (Confirmed baseline, extend)

Current Foundation supports drag-to-pan. Proposed additions (Phase B): clamp pan to campus
bounds, optional integer-step zoom levels, keyboard pan (arrows) for accessibility, and
"focus selected node" (also drivable from the NodeList).

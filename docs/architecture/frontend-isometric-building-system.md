# Frontend Isometric Building System (Visual PR B)

- Version: v0.1.0 · Status: Draft (for review/devcto)
- Foundation for building/tile/layer/footprint/depth/asset rendering. **No final
  sprites or state variants** — placeholders only.
- **Visual PR C update:** `BuildingView` now acquires a reference-counted
  `AssetHandle` from the injected app-scoped `AssetManager` and renders a generated
  DEVELOPMENT `Sprite`, with the status border/glyph and the incident badge drawn as
  a SEPARATE overlay (health, selection, incident, and texture are independent). See
  [`frontend-asset-runtime.md`](./frontend-asset-runtime.md).

## Coordinate system (unchanged, UI-D-002)

The 128×64 logical tile and the transforms (`gridToScreen`/`screenToGrid`/
`layoutGrid` in `game/pixi/isometric.ts`) are **unchanged**. New code imports
`TILE_WIDTH=128` / `TILE_HEIGHT=64` from `isometric/coordinates.ts`, which
re-exports the existing transforms — no coordinate meaning changed.

## Scene layers (`scene/sceneLayers.ts`)

Explicit, typed layers created once, back→front:
`ground · grid · connections · buildingBase · buildings · decorations · effects ·
status · selection · debug`. The `buildings` layer is `sortableChildren`; `debug`
is hidden unless explicitly enabled. Selection sits above status/buildings so
overlays are never hidden. The DOM HUD is **not** a Pixi layer.

## Footprint model (`isometric/footprint.ts`)

`TileFootprint {width,height: 1..4}` + `GridPlacement {col,row,footprint}`.
Provides `occupiedTiles`, `intersects`, `baseAnchor` (bottom-center, so taller
final sprites don't shift the base — §12), `centerTop`, `footprintBounds`, and
`selectionPolygon`. Footprint intersection is a **display/validation helper only**
— it does not add any Simulation placement rule.

## Depth sorting (`isometric/depth.ts`)

`depthZIndex(placement)` keys on the footprint's **front tile** `(row+col)` (×1000)
plus a screenY nudge, so nearer/larger buildings draw in front. `compareDepth`
breaks ties on a stable id — never creation order — so a re-sync never reshuffles
equal-depth buildings. The buildings layer sorts via `sortableChildren` (zIndex set
per building on position change), not every frame.

## Anchor / pivot rules (§12)

- Building anchor / pivot: footprint **bottom-center**.
- Grid placement origin: the footprint's base tile (min col,row).
- Selection origin: the footprint bottom face (not the sprite image).
- Label / status-icon origin: building top area.

## BuildingView (`buildings/`)

`BuildingRenderModel` (from `nodeBuildingAdapter`) → `BuildingView` (a Pixi
Container drawing a DEVELOPMENT placeholder: footprint slab + cuboid silhouette +
label). Status uses colour AND border pattern/notches AND the label. `BuildingView`
never calls the API and never subscribes to the store — the scene pushes a model
in. Placeholders are marked `DEVELOPMENT_PLACEHOLDER_NOT_FINAL_ART`.

Unknown node kinds map to a safe `unknown` building ("UNKNOWN" label) so the scene
never breaks (FE-ART-001 partial; full unknown-kind UX stays tracked in FE-ART-001).

## Node health vs visual status (single resolver)

`health` is **optional** (`SnapshotNode.health?`) — the snapshot is a free-form
object and some kinds omit it. `game/nodeStatus.ts` is the **single source of
truth** that maps a node to a display status; every surface (BuildingView,
NodeList, NodeInspector, ARIA) uses it, so canvas and DOM never disagree, and a
missing health is **never shown as Healthy**:

- `enabled === false` → **disabled** (precedence; raw health kept in data).
- health present + known enum → that health (Healthy/Warning/Critical/Down).
- health present but unrecognized → **not_reported**.
- health absent + kind has no health concept (`NODE_HEALTH_CAPABILITY`:
  load_balancer = `not_applicable`) → **not_applicable** ("Health N/A", neutral
  blue-grey, glyph `—`).
- health absent + health-capable kind (app_server/redis/postgresql, or unknown
  kind defaulting to reported) → **not_reported** ("Status unavailable", neutral
  grey, glyph `?`).

Neutral states never reuse green/Warning/Critical/Down colours and always carry a
non-colour glyph + text + ARIA phrase. **Incidents are separate**: a
`not_applicable` load_balancer can still carry an LB_IMBALANCE / NO_HEALTHY_SERVER
incident (shown via the incident panel) — a missing health is never turned into
Critical, and an active incident is never hidden behind a false "Healthy".

Backend decision on whether non-health nodes should emit an explicit
applicability marker is tracked as **BACK-FU-009** (Proposed; no backend change in
this PR). FE-ART-002 (full state-data-source matrix) remains **not complete**.

## Scene diff sync (§27)

`GameScene.sync(nodes, connections)` reuses existing `BuildingView`s (update in
place), creates only new nodes, and destroys only removed nodes — verified at 50
nodes. `GameCanvas` isolates a scene-sync error in a try/catch so a render fault can
never break the zustand notification chain (which would block React's re-render).

## Assets (`assets/`)

- `assetTypes.ts` / `assetManifest.ts`: the runtime `AssetManifest` schema +
  validation (duplicate ids, category/sourceType, anchor 0..1, footprint 1..4,
  missing/cyclic fallbacks).
- `AssetManager.ts`: skeleton owning the manifest, load state (`idle/loading/
  ready/failed`), and shared/generated textures; resolves unknown/missing ids to a
  generated fallback. No final atlas is loaded in PR B.
- `generatedFallback.ts`: an offscreen-canvas "?/UNKNOWN" texture (no binary
  files); never throws (returns null → the scene draws a Graphics placeholder).

## Texture / resource ownership (§20, FE-ART-003 seam — NOT final)

- **AssetManager owns** shared + generated-fallback textures and the manifest.
- **Scene owns** Sprites/Graphics/Containers/listeners.
- `GameScene.destroy()` destroys the Application `{children:true}` (NOT
  `texture:true`) and then calls `AssetManager.dispose()` for its textures.
- FE-ART-003 (final shared-atlas lifecycle + cache invalidation) is **not
  complete** — this only establishes the ownership seam before real atlases land.

## Debug overlay (`scene/debugOverlay.ts`)

Dev-only footprint outlines + coord/depth labels on the `debug` layer, gated by
`import.meta.env.DEV && VITE_PIXI_DEBUG==='1'`. Off in production; `eventMode:'none'`
so it never blocks pointer input.

## Out of scope (PR B)

Final building/character/decoration sprites, final texture atlas, per-state final
variants, request-flow/cache/DB effects, deploy/rollback animation, FE-ART-002
state-data-source visualization, and any Backend/Simulation/contract change.

## PR C entry gates (unchanged)

FE-ART-002 (state data-source matrix), FE-ART-003 (final shared-texture lifecycle),
ASSET-OPS-001 (full asset metadata schema), ASSET-OPS-002 (numeric budgets), and an
asset-manifest baseline must be done before PR C wires real assets/state visuals.

# Frontend PixiJS Lifecycle

- Version: v0.1.0 · Status: Draft (for review/devcto)

The isometric board is a PixiJS scene wrapped so React owns its lifecycle. Pure
geometry/visual logic is separate from Pixi so it is unit-testable.

## Modules

- `game/pixi/isometric.ts` — grid ↔ screen transforms + deterministic layout
  (pure; no jitter, so a node set always maps to the same cells).
- `game/pixi/nodes.ts` — visual mapping. Status is conveyed by **colour AND icon
  glyph AND label/border pattern**, never colour alone (accessibility).
- `game/pixi/createGameScene.ts` — `GameScene`: the only place Pixi is
  instantiated. Owns the `Application`, a pannable world container, node sprites,
  edges, and selection.
- `game/GameCanvas.tsx` — React wrapper.

## Lifecycle (§26)

1. `GameCanvas` mounts → `GameScene.create(host)` (async `Application.init`).
2. A `cancelled` guard destroys the scene if the component unmounts before
   `create()` resolves (prevents a leaked orphan Application).
3. The scene subscribes to the store and `sync()`s nodes + connections and
   `setSelection()` on every change.
4. On unmount: unsubscribe, `scene.destroy()`.

`GameScene.destroy()` is idempotent and:
- removes the `window` `resize` listener,
- destroys the Pixi `Application` with `{children, texture}` (frees GPU
  resources + child sprites/listeners),
- drops all sprite references,
- makes subsequent `sync()`/`setSelection()` no-ops.

## Selection sync

Clicking a sprite (`pointertap`) and clicking the accessible `NodeList` both drive
the same store `selectedNodeId`, so the canvas and the DOM list stay in sync. The
`NodeList` is the keyboard/screen-reader alternative to canvas interaction. When a
snapshot update removes the selected node (e.g. REMOVE_NODE), the store clears
`selectedNodeId` so no destroyed node stays selected (§8).

## Performance (§26)

- The Pixi `Application` is created once per mount, never on React re-render.
- The store subscription diffs and updates sprites; no snapshot deep-copy per
  event.
- `recent_event_ids` is a bounded set; the event log is capped.

## Building system + resource ownership (Visual PR B)

The scene now uses explicit layers, footprints, stable depth, `BuildingView`s, and
an `AssetManager`. Ownership is split (§20): the AssetManager owns shared/generated
textures + the manifest; the scene owns Sprites/Graphics/Containers/listeners.
`GameScene.destroy()` destroys the Application `{children:true}` (NOT `texture:true`)
then calls `AssetManager.dispose()`. `GameCanvas` wraps scene sync in try/catch so a
render error cannot break the store→React notification chain. FE-ART-003 (final
shared-atlas lifecycle) is not complete. Full detail:
[frontend-isometric-building-system.md](frontend-isometric-building-system.md).

## Testing

`GameScene` is tested with a shared `vi.mock('pixi.js')` fake
(`tests/helpers/fakePixi.ts`) to assert create/sync/select/resize/destroy, diff
reuse, and listener cleanup without WebGL. `GameCanvas` is tested by mocking
`createGameScene` to assert create-on-mount and destroy-on-unmount. Pure modules
(footprint/depth/manifest/adapter/asset-manager) have standalone unit tests.

## Deferred

Real art assets, building/flow animations, camera zoom, and fine-grained live
node-health repaint from individual events (currently the board refreshes from the
snapshot; incremental per-event health mutation is a follow-up).

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
`NodeList` is the keyboard/screen-reader alternative to canvas interaction.

## Performance (§26)

- The Pixi `Application` is created once per mount, never on React re-render.
- The store subscription diffs and updates sprites; no snapshot deep-copy per
  event.
- `recent_event_ids` is a bounded set; the event log is capped.

## Testing

`GameScene` is tested with `vi.mock('pixi.js')` (fake Application/Container/
Graphics/Text) to assert create/sync/select/resize/destroy and listener cleanup
without WebGL. `GameCanvas` is tested by mocking `createGameScene` to assert
create-on-mount and destroy-on-unmount.

## Deferred

Real art assets, building/flow animations, camera zoom, and fine-grained live
node-health repaint from individual events (currently the board refreshes from the
snapshot; incremental per-event health mutation is a follow-up).

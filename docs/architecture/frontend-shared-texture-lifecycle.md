# Shared Texture Lifecycle Policy (FE-ART-003)

- Owner: Frontend Architecture · Status: **FE-ART-003 Policy: APPROVED_WITH_FOLLOW_UP**
- Runtime implementation (Visual PR C): **IMPLEMENTED_IN_DEV** — see
  [`frontend-asset-runtime.md`](./frontend-asset-runtime.md) (FU-001..004). This
  document remains the policy of record; the runtime doc records what was built.

Defines creation / acquire / release / destroy / version-swap ownership for shared
textures, atlases, and scene resources, so PR C can load real atlases without
leaks, double-frees, or a false "Healthy"-style texture reuse. Aligns with the
already-implemented AssetManager ownership seam (Visual PR B) and the Ops asset
policies (ASSET-OPS-001/002).

## 1. Ownership model (final policy)

**Application `AssetManager` owns:** shared Texture, Texture Atlas (+ frame subtextures),
generated fallback Texture, Manifest registry, asset load state, versioned cache,
in-flight load Promise.

**`GameScene` owns:** Sprite, Graphics, Container, Text, hit area, pointer handlers,
`ConnectionView`, `SelectionView`, debug objects, scene-only transient RenderTexture.

**React component owns:** DOM UI, asset-load status display, scene mount/unmount
requests (via `GameCanvas`).

**Prohibited:** a Scene destroying a shared Texture; a React component owning a
Pixi Texture; a Sprite `destroy` cascading into a shared Texture; disposing the
whole AssetManager on every route change.

## 2. AssetManager scope (final policy)

- **One AssetManager instance per Frontend runtime**, shared by all GameScenes /
  sessions.
- Route change / session switch: the Manager is **kept**; only the Scene is destroyed.
- `disposeAll()` runs only at app teardown, explicit hard reset, or a test teardown.
- **Created in App bootstrap and injected into GameScene** (constructor/factory
  param) — not a hidden module-global singleton. Tests use an independent instance.
- Visual PR B currently creates a scene-scoped AssetManager (only a generated
  fallback, no shared atlas). **Migration (PR C):** hoist the AssetManager to app
  bootstrap and inject it; the scene stops owning/disposing it. Tracked as
  **FE-ART-003-FU-001**.

## 3. Asset Handle contract

Scenes acquire a **handle**, never a raw Texture:

```
interface AssetHandle { assetId: string; version: string; texture: Texture; release(): void; }
```

- `acquire(assetId, version?)` shares an idempotent load; same `assetId+version`
  yields the **same** Texture (one GPU upload).
- The Scene calls `release()` on teardown; `release()` decrements a refcount and does
  **not** immediately destroy the Texture.
- Refcount/pin policy: a Texture is eligible for eviction only at refCount 0; the
  Manager may keep it cached (LRU/pinned per ASSET-OPS-002) rather than free
  eagerly. Double `release()` is a safe no-op; using a released handle is a dev-time
  error (guarded, returns fallback in production).

## 4. Cache key & versioning

- Cache key = `assetId + assetVersion`; atlas frame = `atlasId + atlasVersion + frameName`.
- A new version of an `assetId` does **not** silently overwrite the existing Texture;
  different versions are distinct cache entries.
- During a manifest swap, existing Scenes keep their current handles; new Scenes get
  the new version; old-version textures are collected once their refCount hits 0.
- Cache-busting relies on `assetVersion`, not only a URL query string; identical
  binaries are de-duplicated via `checksum` (ASSET-OPS-001).

## 5. Load state

States: `idle → loading → ready → failed → stale → disposed`.
- Concurrent `acquire`/`preload` of the same key share one Promise.
- `failed` does not auto-retry infinitely; retry count/actor follows the Ops manifest
  policy (ASSET-OPS-002: ≤2 retries, backoff). After exhausting retries → fallback handle.
- Manifest version change marks superseded entries `stale`.
- `acquire` on a `disposed` Manager throws (dev) / returns fallback (prod), never
  registers a Texture into a disposed Manager.

## 6. Texture destruction matrix

| Resource | Owner | Scene destroy | Route change | Manifest update | App teardown |
|---|---|---|---|---|---|
| Shared atlas texture | AssetManager | Keep | Keep | Stale/retain until refCount 0 | Destroy |
| Shared image texture | AssetManager | Keep | Keep | Stale/retain until refCount 0 | Destroy |
| Generated fallback | AssetManager | Keep | Keep | Keep (re-version if changed) | Destroy |
| Sprite | Scene | Destroy | Destroy | Replace as needed | Destroy |
| Graphics | Scene | Destroy | Destroy | Replace as needed | Destroy |
| Text | Scene | Destroy | Destroy | Replace as needed | Destroy |
| Scene RenderTexture | Scene | Destroy | Destroy | Destroy | Destroy |
| Pointer handler | Scene | Remove | Remove | Remove if view replaced | Remove |
| ConnectionView / SelectionView | Scene | Destroy | Destroy | — | Destroy |

**Pixi v8 destroy API:** scene teardown uses `app.destroy(true, { children: true })`
(NOT `{ texture: true }`); display objects use `container.destroy({ children: true })`.
Shared textures are freed only by `AssetManager.dispose()` → `texture.destroy(true)`.
This matches the current `createGameScene.ts` seam.

## 7. Scene lifecycle

**Create:** build layers → inject AssetManager → `acquire` needed assets → create
Sprites → register handlers.
**Snapshot sync:** reuse existing handles; do NOT re-acquire if `assetId+version`
unchanged; swap a handle only when the required asset (kind/version) changes
(`release` old, `acquire` new).
**Destroy (order):** remove listeners → destroy Scene views → `release` scene handles
→ destroy scene-only RenderTextures → destroy layers/containers → **keep shared
assets**. A blanket `destroy({ texture: true })` is prohibited.

## 8. Fallback policy

Priority: (1) manifest `fallbackAssetId` → (2) category fallback → (3) generated
universal fallback. Chain depth ≤ 3 (per ASSET-OPS-002); cycles blocked at manifest
validation; fallbacks use the same handle policy; the generated universal fallback is
one shared texture (never per-node); a fallback failure must not crash the Scene.

## 9. Session / route / HMR

- **Session switch:** destroy Scene → release scene handles → keep shared assets →
  create new Scene.
- **Route leave:** destroy Scene only; keep Manager.
- **HMR (dev):** detect a duplicate AssetManager and reset the previous one so old
  textures aren't double-held; production has no HMR reset path. Keep HMR and prod
  policies separate.
- **Tests:** an independent Manager per test; after `disposeAll()` no leftover
  textures or pending Promises.

## 10. Concurrency & dispose races

- Same-asset concurrent `acquire`: one shared Promise, one Texture.
- Scene destroyed mid-preload: the load resolves but its result is released/ignored
  by that scene; never attaches to a destroyed scene.
- Manifest swap mid-acquire: the acquire resolves against the version it started with.
- Retry in flight during route leave / dispose: aborted or its result discarded.
- A load completing after `dispose` must NOT register into the disposed Manager.
- No unhandled promise rejections (all load Promises have a rejection path → fallback).

## 11. Error & logging

- Production: provide a fallback; distinguish an **asset error** from a **backend
  error**; never expose internal paths/stack.
- Dev: log `assetId`, `version`, `source`, failure stage, and whether a fallback was
  used; suppress duplicate repeats; never log per snapshot-poll.

## 12. Gap vs current code (implementation follow-ups, PR C)

- **FE-ART-003-FU-001:** hoist AssetManager to app bootstrap + inject into GameScene
  (today it is scene-scoped and disposed on scene destroy — safe now because only a
  generated fallback exists, but must change before shared atlases).
- **FE-ART-003-FU-002:** implement `AssetHandle` + refcount/versioned cache in
  AssetManager (skeleton today resolves everything to the fallback).
- **FE-ART-003-FU-003:** HMR duplicate-manager reset.
- **FE-ART-003-FU-004:** concurrency/abort handling for real atlas loads.

## 13. FE-ART-003 completion criteria

Owner matrix, AssetManager scope, Asset Handle contract, versioned cache, scene
destroy order, fallback ownership, HMR/test reset, and concurrency/dispose-race
policy all defined (done here) AND consistent with the Ops manifest policy
(ASSET-OPS-001/002) AND reviewed by Frontend Architecture + Ops + DevCTO.

**Current status: FE-ART-003 = REVIEW_PENDING.**

# Frontend Asset Runtime (Visual PR C implementation)

- Owner: Frontend · Status: **FE-ART-003 Runtime: IMPLEMENTED_PENDING_REVIEW**
- Implements FE-ART-003-FU-001..004 against the FE-ART-003 policy
  (`frontend-shared-texture-lifecycle.md`). No final production sprites/atlases —
  only code-generated DEVELOPMENT assets + a universal fallback.

## Files

| File | Role |
|---|---|
| `src/game/pixi/assets/AssetManager.ts` | App-scoped runtime: versioned cache, handles, refCount, manifest replace, retry, races, dispose |
| `src/game/pixi/assets/assetLoader.ts` | `AssetLoader` seam + `AssetLoadError` taxonomy + `GeneratedAssetLoader` (dev textures) |
| `src/game/pixi/assets/retry.ts` | Retry state machine (1 + ≤2 retries, 8s/attempt, 250→750ms), injectable sleep |
| `src/game/pixi/assets/generatedBuildingAsset.ts` | Per-kind DEVELOPMENT canvas assets, node-kind→assetId map, dev manifest builder |
| `src/game/assetRuntimeContext.tsx` | App-scoped provider (bootstrap create, inject, HMR reset) |
| `src/game/visualSource.ts` | Client Runtime Source Classes (POLICY-C-FU-001) |
| `src/game/incidentModel.ts` | Incident dedupe / phase / overflow (POLICY-C-FU-003) |

## Ownership (FE-ART-003 §1)

- **AssetManager** (one per runtime, created in `AppProviders` via `AssetRuntimeProvider`,
  injected into `GameScene` via `GameSceneOptions.assets`) owns shared textures, the
  generated fallback, the manifest registry, and the versioned cache. A scene NEVER
  disposes an injected manager — `GameScene.destroy()` only disposes a *scene-owned*
  fallback manager (older callers/tests).
- **GameScene / BuildingView** own Sprites/Graphics/Containers/listeners and hold
  `AssetHandle`s; on destroy or texture swap they `release()` the handle. They never
  destroy a shared texture.

## Asset Handle + cache (FE-ART-003 §3–§4)

- `acquire(assetId)` → `AssetHandle { assetId, assetVersion, texture, fallback, released, release() }`.
- Cache key = `assetId@assetVersion` (a new version is a distinct entry; an existing
  scene keeps its handle/texture). `checksum` is integrity only — never a cache key.
- Same key → same `Texture` and one shared in-flight load promise (one upload).
- `release()` decrements refCount and does NOT destroy; double release is a safe
  no-op. A stale entry is freed only once refCount hits 0 (`disposeStale()` / on release).

## Load state + retry (§5, POLICY-C-FU-004)

- Cache states: `idle → loading → ready → failed → stale → disposed`.
- Retry: initial + ≤2 retries (3 attempts max), 8s per-attempt timeout, backoff
  250ms then 750ms. Retryable: `network` / transient `server` (5xx) / `timeout`.
  Never retried: `client` (4xx) / `not_found` / `schema` / `manifest` / `license` /
  `approval` / `decode`. Abort stops everything.
- After retries exhaust → the bounded fallback chain (below).

## Fallback chain (§8)

Priority: entry `fallbackAssetId` → (implicit) universal fallback. Depth ≤ 3, cycles
guarded (a repeated id short-circuits to the terminal generated fallback, which never
fails). A fallback handle is flagged `fallback: true`. Fallback ≠ node Down; an asset
error is distinct from a backend error.

## Manifest replacement + rollback (§15)

`replaceManifest(next)` validates; a blocking-invalid manifest (DUP_ID / FALLBACK_CYCLE)
is rejected and the last good manifest is kept. Otherwise entries whose current
version differs are marked `stale` (existing handles keep working), the registry +
`manifestVersion` are swapped, and unreferenced stale entries are collected. Rollback
= replace with the previous manifest.

## Concurrency / dispose races (§21)

- Concurrent acquire of the same key shares one promise/texture.
- Scene destroyed mid-load → its handle is released (or the resolved handle released
  if the view is already gone); the manager keeps the shared load.
- Manager disposed mid-load → `lifecycle` AbortSignal fires; a load that still
  completes is discarded and its texture destroyed — never registered into a disposed
  manager. No unhandled rejections.

## HMR + tests (§22–§23)

- `resetForHmr()` disposes textures/loads and re-arms the manager; the provider keeps
  the prior instance in an `import.meta.hot` slot and resets it on replacement.
  Production has no HMR reset path.
- Tests inject their own `AssetManager` (fake loader + injected `sleep`, so retry
  backoff never waits real time) and `disposeAll()` on teardown.

## Not in this PR

No final sprites/atlases, no EVENT_DERIVED effects, no request-flow particles, no
mipmaps, no 4096² textures, no asset CI, no backend/simulation/OpenAPI change. See
`../game-design/ui-art-direction/visual-pr-c-policy-gates.md` for the remaining gates
(POLICY-C-FU-002 event lifecycle; -005..010 + ASSET-OPS-004 before first production
asset).

# Frontend Asset Runtime (Visual PR C implementation)

- Owner: Frontend · Status: **FE-ART-003 Runtime: IMPLEMENTED_IN_DEV** (Visual PR C merged to dev)
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

## Fallback chain (§8) — three tiers

Ordered by the ORIGINAL request (linear, not per-entry recursive):

1. **primary** — the requested `assetId`
2. **entry** — the primary's `fallbackAssetId`
3. **category** — `manifest.categoryFallbacks[primary.category]` (defined once at the
   manifest level; never hardcoded per component)
4. **universal** — the generated universal fallback (terminal, never fails)

`resolveTiered()` in `AssetManager` is the single resolver; `BuildingView` never
decides fallback order. Each tier uses the same acquire/load/cache/handle policy; a
non-primary tier flags the handle `fallback: true`, and `lastTierOf(assetId)` exposes
the tier used (diagnostics/tests).

**Depth & cycles:** at most **3 fallback hops** (primary excluded); a 4th hop is
never entered. Because the sequence is built from the original request only, a
duplicate candidate id (e.g. category fallback == primary, or entry == category) is
loaded **at most once** (`tried` set) and cannot form a cycle. Manifest validation
also rejects entry-fallback cycles (`FALLBACK_CYCLE`) and missing/invalid category
fallbacks (`MISSING_CATEGORY_FALLBACK` / `BAD_CATEGORY_FALLBACK_KEY`). Fallback ≠ node
Down; an asset error is distinct from a backend error.

## Checksum verification + bounded integrity refetch (POLICY-C-FU-005)

The loader returns `LoadedAsset { texture, computedChecksum? }`. When a manifest entry
declares a `checksum`, the manager compares it (case/prefix-insensitive via
`normalizeChecksum`) against the loaded `computedChecksum`:

- **match** (or no declared checksum) → accept.
- **declared but no computed value** → treated as a mismatch (cannot verify → not
  accepted).
- **mismatch** → destroy the corrupt texture, then perform **exactly one** integrity
  refetch (`mode: 'integrity_refetch'`, `bypassCache: true`) — NOT part of the
  transient retry loop. A second mismatch throws `checksum_mismatch` → the fallback
  chain. A network/decode error on the refetch goes straight to fallback (no retry).

**Attempt bound:** normal load = 1 + ≤2 transient retries (3); integrity refetch = 1
→ **≤ 4 total network attempts**. Concurrent consumers of the same key share one load
promise and therefore **one** integrity refetch. A checksum verified while the manager
is being disposed discards the texture and never registers it. `ChecksumVerifier`
(`WebCryptoChecksumVerifier`) is the SHA-256 boundary a real loader uses; internal
checksums are never surfaced to the UI. Generated development assets declare no
checksum, so verification is skipped for them.

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

## Scene-local manager guard (§19)

Production injects the app-scoped manager via `AssetRuntimeProvider`. An uninjected
`GameScene` **throws in production** and **warns once in dev**; a scene-owned local
manager is only created with the explicit `allowLocalAssetManagerForTests` option
(tests/legacy harnesses). No silent per-route manager creation.

## Known dev-only limitation (follow-up)

Under React StrictMode with **no** `import.meta.hot` data channel (an unusual dev/
preview config; vite dev always provides one), an uninjected provider's first
transient manager is not disposed on the StrictMode remount — the committed manager is
live and correct, but the first is dev-only garbage. Vite dev (HMR slot) and
production (single mount) are unaffected. Tracked as a non-blocking follow-up.

## Real-browser verification

The fallback/checksum/race paths run in real Chromium/WebGL2 via a test-only harness
(`frontend/tests/browser/asset-runtime/`, `pnpm test:browser:asset-runtime`) that
injects a `ControlledAssetLoader` through the AssetManager's public `loader` DI — no
production hook, excluded from the production bundle. A full-app smoke
(`pnpm test:browser:visual-c`) covers single-canvas/single-socket, 54 nodes, route×10,
and both viewports against the real app. See
[`../operations/visual-pr-c-live-verification.md`](../operations/visual-pr-c-live-verification.md).

## Not in this PR

No final sprites/atlases, no EVENT_DERIVED effects, no request-flow particles, no
mipmaps, no 4096² textures, no asset CI, no backend/simulation/OpenAPI change. See
`../game-design/ui-art-direction/visual-pr-c-policy-gates.md` for the remaining gates
(POLICY-C-FU-002 event lifecycle; -005..010 + ASSET-OPS-004 before first production
asset).

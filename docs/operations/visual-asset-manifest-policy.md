# Visual Asset Manifest Operational Policy

- Owner: Infra/Platform · Status: **Manifest Operational Baseline: REVIEW_PENDING**
- Base: dev `65adf13`. Documentation only — no manifest binary, no CI workflow, no
  final atlas. Extends the runtime manifest already validated in Visual PR B
  (`frontend/src/game/pixi/assets/assetManifest.ts`).

Defines the operational runtime-manifest shape, versioning, bundles, fallback, the
future CI contract (ASSET-OPS-004), and loading/recovery. Links to
`visual-asset-metadata-schema.md` (ASSET-OPS-001) and `visual-asset-budget.md`
(ASSET-OPS-002).

## Runtime manifest (required top-level)

`manifestVersion`, `generatedAt`, `buildId` (or `assetBundleVersion`), `assets`,
`bundles`.

### Asset entry (minimum)
`assetId`, `assetVersion`, `category`, `sourceType`, `source`, `frame` (atlas),
`anchor`, `footprint`, `fallbackAssetId`, `bundleId`, `checksum`.

Runtime manifest ↔ Production Metadata link on `assetId + assetVersion`. The PR B
validator already covers: version present, duplicate id, category/sourceType,
source (image/atlas), atlas frame, anchor 0..1, footprint 1..4, missing/self/
multi-level fallback cycle. This policy adds the operational fields (`checksum`,
`bundleId`, `assetVersion`, `buildId`) and the CI contract below.

## Versioning

- **Schema version** and **asset bundle version** are separate; a breaking schema
  change bumps schema major.
- Any content change to an `assetId` **requires** an `assetVersion` change.
- Cache key includes `assetId + assetVersion` (see FE-ART-003).
- Manifest-only change with unchanged binaries → verified by `checksum`.
- Rollback to a previous manifest must remain possible.

## Bundles

Recommended: `core-ui`, `campus-base`, `functional-buildings`, `status-effects`,
`optional-decorations`, `characters-phase2`.

Visual MVP initial preload: `core-ui`, `campus-base`, the required part of
`functional-buildings`, and `fallback`. The rest may lazy-load.

## Fallback

Priority: entry `fallbackAssetId` → category fallback → generated universal
fallback. Max chain depth **3**; cycles blocked at validation; non-production-
approved assets may not be used as fallback; the universal generated fallback is
always available; fallback use may be logged via telemetry/diagnostics.

## CI contract (ASSET-OPS-004 — IMPLEMENTATION_PENDING)

Checks to implement later (this PR defines the contract, not the workflow):
schema validation; duplicate `assetId+version`; duplicate frame; source file
exists; atlas JSON↔image consistency; frame-name convention; anchor range;
footprint range; fallback exists; fallback cycle; fallback chain depth; checksum;
license metadata present; production approval; texture dimension; atlas dimension;
compressed bundle size; estimated GPU memory; unused manifest entry; runtime asset
absent from manifest. **No workflow code in this PR.**

## Loading failure & recovery

Preload progress; per-bundle timeout; limited retry (ASSET-OPS-002); fallback;
partial run on optional-bundle failure; distinguish **critical** vs **optional**
bundle failure; distinguish **asset error** from **backend error**; on version
mismatch discard stale cache / request the new version; never expose internal
paths/stack to users.

## Status
- **ASSET-OPS-001: REVIEW_PENDING**
- **ASSET-OPS-002: REVIEW_PENDING**
- **Asset Manifest Operational Baseline: REVIEW_PENDING**
- **ASSET-OPS-004 (manifest CI): IMPLEMENTATION_PENDING**

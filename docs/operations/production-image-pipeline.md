# Production Image Pipeline — Generator & Loader Boundaries (P3A)

- Owner: Frontend/Program · Status: **P3A: IMPLEMENTED_PENDING_REVIEW**
- Implements the P3A half of APE-P3-FU-001: a **Python build-time** Metadata→Manifest
  generator + the **TypeScript** Production Image Loader. Atlas is **BLOCKED_BY_P3B**.

## Responsibility split (aligned by construction)

**Python build-time tool (`tools/asset_ops`)** owns everything governance/derivation:

- reads Production Metadata (`assets/metadata/**`) + `assets/generator-config.json`
- approval/inclusion filter, metadata→entry mapping, canonical serialization, `build_id`
- `categoryFallbacks` assembly, mapping/exclusion reports, build metadata, rollback index

It imports the shared primitives from `canonical.py` **directly** — no duplicated
inclusion predicate, mapping, serialization, or `build_id`:
`has_production_approval`, `is_production_includable`, `canonical_included_metadata`,
`metadata_to_entry`, `canonical_bytes`, `canonical_manifest_bytes`, `build_id_envelope`,
`compute_build_id`, and the governance-exclusion set. Because the validator (P2) uses the
same primitives, **generator output passes `asset-production-gate` by construction**.

**TypeScript runtime** owns only consumption:

- consumes the generated Runtime Manifest JSON (never re-derives approval/mapping/build_id)
- routes by `sourceType`, fetches images, computes checksums, decodes, builds textures

TypeScript must **not** re-implement the approval filter, inclusion, metadata→entry
mapping, canonical serialization, `build_id`, or exclusion classification.

## CLI

```
python -m tools.asset_ops generate         --workspace <ws>   # assemble manifest + reports
python -m tools.asset_ops verify-generated --workspace <ws>   # regenerate, diff, run P2 gate
python -m tools.asset_ops validate         --workspace <ws>   # C01-C26 (ASSET-OPS-004)
```

Exit codes — `generate`: 0 success · 1 metadata/policy violation · 2 input · 3 internal.
`verify-generated`: 0 all-checks-pass · 1 non-deterministic / persisted-baseline drift /
report-schema / P2 gate-fail / policy violation · 2 input · 3 internal.

**`verify-generated` verifies** (1) **deterministic regeneration of ALL outputs** (generate
twice, compare every artifact byte-for-byte), (2) **drift of the persisted
source-controlled baselines** (Runtime Manifest, Build Metadata, Rollback Index) vs the
workspace, (3) **report schema** (required fields, no absolute host paths), and (4) **P2
validator compliance** (C01–C26). It does **not** treat the ephemeral CI reports
(Mapping/Exclusion/Validation) as source-controlled baselines — those are regenerated
every run and checked for A/B byte-stability + schema, not repository drift.

### Generator outputs

| Output | Path | Lifecycle | verify-generated |
|---|---|---|---|
| Runtime Manifest | `assets/generated/manifests/manifest.json` | **persisted baseline** · committed · runtime-consumed | drift-checked |
| Build Metadata | `assets/generated/build-metadata.json` | **persisted baseline** · release · audit | drift-checked |
| Rollback Index | `assets/releases/rollback-index.json` | **persisted baseline** · release · rollback | drift-checked |
| Mapping Report | `assets/generated/reports/mapping-report.json` | CI-only · audit · not runtime-consumed | A/B byte-stability + schema |
| Exclusion Report | `assets/generated/reports/exclusion-report.json` | CI-only · audit · not runtime-consumed | A/B byte-stability + schema |
| Validation Summary | `assets/generated/reports/validation-summary.json` | CI-only · audit · not P2-report substitute | A/B byte-stability + schema |

The Runtime Manifest is byte-deterministic (sorted keys, `assets` by
`assetId+assetVersion`, sorted `categoryFallbacks`, UTF-8, LF, no timestamps/hostnames/
absolute paths). Inclusion is decided ONLY by `canonical.is_production_includable`;
exclusions are reported in the exclusion report (never silent): DEPRECATED = non-blocking
exclude; REVOKED, DRAFT/*_REVIEW/*_REJECTED (P1 approval-workflow §4 — hard error in
production generation input), approval mismatch, invalid license = blocking. An approved
**atlas** asset is not runtime-ready in P3A: it is a hard error, recorded in the exclusion
report as `ASSET_ATLAS_BLOCKED_BY_P3B` (merge_blocking, referenced in the validation
summary too) and excluded from the manifest/build_id — never converted to an image or
generated entry (First Production Atlas Asset Gate CLOSED). The generator does **not**
re-run C01-C26 — the P2 validator (`verify-generated` also invokes it) is the gate.

**Fallbacks:** the generator emits `categoryFallbacks` matching the runtime resolver
(`primary → entry → categoryFallbacks[primary.category] → universal`, linear/non-recursive).
It never builds a transitive combined graph or category-target recursion. Only
`source_type == image` is runtime-ready; an approved atlas is a hard error
(BLOCKED_BY_P3B).

## Runtime loader

`frontend/src/game/pixi/assets/productionImageLoader.ts`:

- **`ProductionImageAssetLoader`** — fetches `entry.source`, classifies HTTP
  (404/other-4xx terminal; 5xx/network transient; abort canceled), checks Content-Type,
  computes SHA-256 of the received bytes (Web Crypto), decodes via `createImageBitmap`
  (HTMLImageElement fallback), builds a Pixi Texture, returns `{ texture, computedChecksum }`.
  It **does not** compare checksums or fall back — the AssetManager owns comparison, the
  single bounded integrity refetch (cache-bypassing), the ≤4 attempt cap, corrupt-texture
  destroy, and fallback.
- **`RoutingAssetLoader`** — dispatches by `sourceType`: `generated → GeneratedAssetLoader`,
  `image → ProductionImageAssetLoader`, `atlas → 'unsupported'` error (never silently
  generated). It is the AssetManager's default loader; the existing
  `GeneratedAssetLoader` / manifest / cache / handle / refCount / dispose invariants are
  unchanged.

## Tests

- Python: `pytest tests/asset_ops/test_generator.py` (inclusion/exclusion, mapping,
  categoryFallbacks, determinism, build_id, `verify-generated` drift, P2 integration,
  no-shadow-inclusion, atlas-blocked).
- Frontend: `tests/game/productionImageLoader.test.ts` (loader + routing units) and
  `tests/game/productionImageRuntime.test.ts` (checksum/refetch/fallback/concurrency/
  dispose/version via the AssetManager). Existing AssetManager scenarios unchanged.
- Browser (`pnpm test:browser:production-image`): real Chromium/WebGL2 — synthetic PNGs
  via object URLs, real fetch/Web-Crypto/decode/Texture, checksum-mismatch fallback, 404,
  concurrency, dispose race, version isolation, atlas-unsupported; 0 console/page/WebGL
  errors.

## Bundle separation

The Python generator, the synthetic fixtures, and the browser harness are all
build/test-only — none enter the production bundle. `src/main.tsx` does not import the
generator or any harness; the production loader is the only new runtime code.

## Still pending (out of P3A scope)

Required-check enforcement was completed separately (P2-OPS-FU-001). P3B (production
atlas loader), P4 dry-run, budget confirmation, and opening the First Production Asset
Gate remain **NOT_STARTED / CLOSED**. No production assets or metadata are added.

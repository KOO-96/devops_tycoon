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
`verify-generated`: 0 identical+gate-pass · 1 drift or gate-fail · 2 input · 3 internal.

### Generator outputs

| Output | Path | Disposition |
|---|---|---|
| Runtime Manifest | `assets/generated/manifests/manifest.json` | committed · runtime-consumed |
| Build Metadata | `assets/generated/build-metadata.json` | release artifact |
| Mapping Report | `assets/generated/reports/mapping-report.json` | CI artifact (audit) |
| Exclusion Report | `assets/generated/reports/exclusion-report.json` | CI artifact (audit) |
| Validation Summary | `assets/generated/reports/validation-summary.json` | CI artifact (audit) |
| Rollback Index | `assets/releases/rollback-index.json` | release artifact |

The Runtime Manifest is byte-deterministic (sorted keys, `assets` by
`assetId+assetVersion`, sorted `categoryFallbacks`, UTF-8, LF, no timestamps/hostnames/
absolute paths). Inclusion is decided ONLY by `canonical.is_production_includable`;
exclusions are reported (never silent): DEPRECATED = non-blocking exclude; REVOKED,
DRAFT/review, approval mismatch, invalid license = blocking. The generator does **not**
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

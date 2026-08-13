# Production Image Budget Confirmation — DevCTO Verdict

- Owner: DevCTO (Program/Ops/Frontend inputs) · Review base: **origin/dev `be9e268`**
- **Docs-only. No product code, no new budget number, no production asset, no gate opened.**
- Confirms the **Production Image ASSET budget** items (the FU-005–010 scope) from PROPOSED →
  **CONFIRMED**, per the per-item state model in `production-asset-budget-confirmation.md §1`
  (`PROPOSED → MEASURED → REVIEWED → CONFIRMED`, confirmed **per item, not all-at-once**).
- Numbers of record are unchanged and stay in `visual-asset-budget.md` — **nothing is
  re-numbered here.**

## 1. Review base

- dev HEAD `be9e268`; `asset-production-gate` green on dev; working tree clean.
- Canonical evidence present in dev: FU-008 (`production-image-swap-peak-budget.md`),
  FU-009 (`first-production-image-fu009-transfer-evidence.md`), FU-010
  (`first-production-image-fu010-hardware-gpu-evidence.md`), plus
  `visual-asset-budget.md`, `production-asset-budget-confirmation.md`, and the
  `asset-production-gate` validator (C15/C16/C17/C18).

## 2. Canonical target inventory (all PROPOSED items) + verdict

Enforcement is **aligned by construction**: validator constants equal the policy numbers —
`TEXTURE_RECOMMENDED=2048`, `TEXTURE_HARD_MAX=4096`, `CRITICAL_GPU_BYTES=32 MiB`,
`RESIDENT_GPU_BYTES=64 MiB`, `CRITICAL_TRANSFER_BYTES=8 MiB`;
`gpu_bytes = w·h·4`, mip `×4//3`.

| # | Canonical item | Value (PROPOSED) | Unit / basis | Enforcement | Supporting FU | Verdict |
|---|---|---|---|---|---|---|
| 1 | Texture recommended dimension | 2048×2048 | px | **C15** (warn > rec) | FU-005 | **CONFIRMED** |
| 2 | Texture hard-max | 4096×4096 (exception-only) | px | **C15** (err > max, waivable) | FU-005 / FU-007 | **CONFIRMED** |
| 3 | Critical transfer bytes | ≤ 8 MiB | BUNDLE_LEVEL_COMPRESSED_TRANSFER | **C17** | FU-009 | **CONFIRMED** |
| 4 | Critical GPU memory | ≤ 32 MiB | GPU_TEXTURE_BYTES_ESTIMATED (RGBA8, mip-aware) | **C18** (critical set) | FU-006 / FU-010 | **CONFIRMED** |
| 5 | Total resident GPU memory | ≤ 64 MiB | MIPMAPPED_GPU_TEXTURE_BYTES_ESTIMATED | **C18** (resident) | FU-006 / FU-008 / FU-010 | **CONFIRMED** |
| 6 | Manifest swap peak | ≤ 64 MiB, `OLD_PLUS_NEW_RESIDENT_COEXISTENCE` | mip-included resident estimate | swap-peak policy (static bound = P4-BUDGET-FU-001, deferred) | FU-008 / FU-010 | **CONFIRMED** |
| 7 | Atlas dimension / pad / extrude | 2048² rec / 4096² max; pad ≥2px; extrude ≥1px | px | C16 | (atlas track) | **REQUIRES_MORE_EVIDENCE** — P3B/Atlas NOT_IMPLEMENTED (out of image scope) |
| 8 | Critical atlas count | ≤ 2 | count | (atlas assembly) | (atlas track) | **REQUIRES_MORE_EVIDENCE** — out of image scope |
| 9 | Cold load time | ≤ 4 s | seconds | — (no validator) | none in FU-005–010 | **REQUIRES_MORE_EVIDENCE** — runtime-perf, not measured |
| 10 | Warm load time | ≤ 1.5 s | seconds | — | none | **REQUIRES_MORE_EVIDENCE** — runtime-perf, not measured |
| 11 | Attempt timeout | 8 s | seconds | — | none | **REQUIRES_MORE_EVIDENCE** — runtime-perf, not measured |
| 12 | Animated sprite count | ≤ 48 | count | — | none | **REQUIRES_MORE_EVIDENCE** — runtime-perf, out of image scope |
| 13 | Flow marker count | ≤ 128 | count | — | none | **REQUIRES_MORE_EVIDENCE** — runtime-perf, out of image scope |
| 14 | Particle count | ≤ 256 | count | — | none | **REQUIRES_MORE_EVIDENCE** — runtime-perf, out of image scope |

**No number changed. No per-asset transfer target invented** (`PER_ASSET_TRANSFER_TARGET:
NOT_DEFINED`). No item required `TARGET_CHANGE_REQUIRED`.

## 3. FU-005 – FU-010 completion matrix

| FU | Purpose | Evidence | Canonical requirement | Result |
|---|---|---|---|---|
| FU-005 | Texture-size / deterministic generation basis | P3A generator + P4 dry-run; C15/C16 enforce dims | metadata canonical + deterministic generation (`production-asset-metadata-policy.md §1/§9`) | **COMPLETE** |
| FU-006 | Mipmap / GPU-memory formula | `gpu_bytes` (RGBA8 ×4, mip ×4/3); C18 mipmap-aware | formula + inputs specified, C18 evaluates mip/no-mip | **COMPLETE** |
| FU-007 | 4096² oversized exception | C15/C16 hard-max + DevCTO waiver; 4096² mip ≈ 85.33 MiB > 64 MiB | exception-only, DevCTO record, reconciled to resident | **COMPLETE** |
| FU-008 | Swap-peak budget | swap-peak policy + hardware lifecycle observed (raw-WebGL2) | method + peak bound (Proposed) + post-cleanup==steady + input contract | **COMPLETE_IN_DEV** |
| FU-009 | Representative transfer measurement | 7 samples, real HTTP + browser ResourceTiming; C17 alignment | tool + fixed boundaries specified + C17 aligns | **COMPLETE_IN_DEV** |
| FU-010 | Hardware-GPU reference environment | Apple M4 Max / ANGLE Metal; game + loader + regression PASS | reference-env spec + template + result record | **COMPLETE_IN_DEV** |

No FU reopened. FU-005/006/007 remain COMPLETE (P3A/P4 evidence); not reopened for this confirmation.

## 4. Validator alignment

- **C17 — ALIGNED.** `c17_bundle_size` sums a critical bundle's on-disk artifact bytes vs
  `CRITICAL_TRANSFER_BYTES` (8 MiB). FU-009 established `C17_static_bytes ≥
  browser_COLD_HTTP_BODY_BYTES` (conservative upper bound; Δ≈0 for identity PNG, ≥0 for
  compressible JSON). C17 never under-counts the browser transfer.
- **C18 — ALIGNED.** `c18_gpu_memory` sums `gpu_bytes(w,h,mipmap=asset.mipmap)` and enforces
  critical ≤ 32 MiB and resident ≤ 64 MiB. Formula = policy formula (RGBA8 ×4, mip ×4/3),
  mipmap-aware per asset. FU-006 formula + FU-010 hardware estimate agree.
- **C15/C16 — ALIGNED.** dimension checks use `TEXTURE_RECOMMENDED`/`TEXTURE_HARD_MAX`;
  4096² is an err (waivable → DevCTO exception), matching FU-007.

## 5. Swap-peak & hardware evidence (FU-008 / FU-010)

- Basis `OLD_PLUS_NEW_RESIDENT_COEXISTENCE` (mip included). Hardware observation (Apple M4 Max
  / Metal): A → A+B coexist → release A → B only; **context loss 0, WebGL error 0**.
- Peak estimate: base 12,582,912 B (12.0 MiB); **canonical mipmapped 16,777,216 B (16.0 MiB)
  ≤ 64 MiB → ~48 MiB headroom**. Post-cleanup `== steady_state(new manifest)`.
- **Scope honesty:** the hardware swap was a `RAW_WEBGL2_TEXTURE_LIFECYCLE` observation; the
  `AssetManager.replaceManifest → stale → disposeStale` path is covered deterministically +
  by the browser suites — **not** claimed as a directly-hardware-measured full AssetManager swap.
- Static swap bound (`steady_resident + max_single_new_resident ≤ 64 MiB`) is a
  `CONSERVATIVE_STATIC_SWAP_PEAK_UPPER_BOUND` (**P4-BUDGET-FU-001**, deferred CI enforcement) —
  **not** an exact runtime VRAM measurement.
- **VRAM terminology:** `GPU_TEXTURE_BYTES_ESTIMATED` + `HARDWARE_GPU_RUNTIME_OBSERVED`;
  **never** `VRAM_MEASURED` (browser exposes no physical VRAM telemetry).

## 6. 4096² policy (unchanged)

4096² RGBA8 = 64 MiB base / ≈ 85.33 MiB mipmapped > 64 MiB resident → **DENIED_BY_DEFAULT +
DEVCTO_EXCEPTION_ONLY** (C15/C16 hard-max err + waiver; C18 resident). This confirmation does
**not** raise the resident budget to accommodate 4096² — the policy keeps 4096² as an exception.

## 7. Runtime follow-up (unchanged)

`BUDGET-RUNTIME-FU-004`: **OPEN / EXCEPTION_ONLY_BLOCKER**. Blocks **only** a non-coexisting
4096² (or equivalent) exception requiring release-before-load orchestration. **Non-blocking**
for normal image readiness, ordinary ≤-budget assets, ordinary coexistence swap, FU-008/009/010,
and a standard-budget first production image candidate.

## 8. DevCTO verdict

| Field | Verdict |
|---|---|
| Target inventory | **PASS** (14 items enumerated) |
| Transfer target (8 MiB) | **CONFIRMED** — BUNDLE_LEVEL, C17; candidate eval `PENDING_FIRST_PRODUCTION_INCLUDED_SET` |
| Resident target (64 MiB) | **CONFIRMED** — MIPMAPPED_GPU_TEXTURE_BYTES_ESTIMATED, C18; 4096² EXCEPTION_ONLY |
| Critical GPU target (32 MiB) | **CONFIRMED** — C18 critical set |
| Dimension targets (2048/4096) | **CONFIRMED** — C15/C16 |
| Swap-peak policy | **CONFIRMED** — OLD_PLUS_NEW_RESIDENT_COEXISTENCE, hardware observed, post-cleanup==steady |
| C17 | **ALIGNED** |
| C18 | **ALIGNED** |
| FU-005…010 | COMPLETE / COMPLETE_IN_DEV (none reopened) |
| Normal-path blocking issues | **NONE** |
| Exception-only issues | BUDGET-RUNTIME-FU-004 (4096² non-coexisting swap) — separate, non-blocking |
| Runtime-perf / atlas items | **REQUIRES_MORE_EVIDENCE** (load-time, timeout, concurrency, atlas) — out of this image-asset scope, remain PROPOSED |

## 9. Budget & readiness decision

- **PRODUCTION_IMAGE_ASSET_BUDGET: `CONFIRMED`** — the per-item image-asset targets (transfer,
  resident, critical-GPU, dimensions, swap-peak) are CONFIRMED. This is scoped to the Production
  Image asset budget covered by FU-005–010; the **runtime-performance targets (cold/warm load,
  attempt timeout, sprite/flow/particle concurrency) and atlas targets remain `PROPOSED`** — not
  in scope, not confirmed (a separate performance / P3B-atlas track).
- **TECHNICAL_READINESS: `READY_FOR_FIRST_PRODUCTION_IMAGE_CANDIDATE`.** Measurement/policy/
  enforcement are ready to evaluate a real production image candidate. This is **not**
  `PRODUCTION_IMAGE_APPROVED`.
- **First Production Image Asset Gate: `CLOSED`** — Budget Confirmation ≠ Gate open.
- **FIRST_PRODUCTION_BUNDLE_TRANSFER_EVALUATION: `PENDING_FIRST_PRODUCTION_INCLUDED_SET`** —
  the actual ≤ 8 MiB bundle verdict is a Gate/C17 step on a real included set.
- `PRODUCTION_BUNDLE_COMPOSITION: NOT_YET_DEFINED`.

## 10. State after this confirmation

```
FU-005: COMPLETE          FU-008: COMPLETE_IN_DEV
FU-006: COMPLETE          FU-009: COMPLETE_IN_DEV
FU-007: COMPLETE          FU-010: COMPLETE_IN_DEV
BUDGET-RUNTIME-FU-004: OPEN / EXCEPTION_ONLY_BLOCKER
Production Image ASSET Budget: CONFIRMED (transfer / resident / critical-GPU / dimension / swap-peak)
Runtime-perf + atlas budget items: PROPOSED (out of scope)
Technical Readiness: READY_FOR_FIRST_PRODUCTION_IMAGE_CANDIDATE
First Production Image Asset Gate: CLOSED
First Production Bundle Transfer Evaluation: PENDING_FIRST_PRODUCTION_INCLUDED_SET
main: untouched · release: none · product code: unchanged · production asset: none
```

## 11. Next track

Not a measurement track anymore. Next: **select a First Production Image candidate** and run
it through the real Production Gate (source asset + metadata + approval + license + provenance +
checksum + category + source type + included set + C01–C26 + C17 bundle transfer + C18 resident
+ generator + ProductionImageAssetLoader + hardware render). The Gate opens only when a real
candidate satisfies every condition.

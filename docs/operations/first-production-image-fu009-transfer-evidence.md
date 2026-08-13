# FU-009 — Representative Transfer Measurement Evidence (POLICY-C-FU-009)

- Owner: Program/Policy · Status: **POLICY-C-FU-009: COMPLETE**
  (final review against the canonical §25 completion contract — see §10; the downstream real-bundle
  ≤ 8 MiB verdict is separated as `FIRST_PRODUCTION_BUNDLE_TRANSFER_EVALUATION: PENDING`)
- Scope: **evidence / measurement tooling only — no product code, no production asset.**
- The 7 images measured here are **NON_PRODUCTION_REPRESENTATIVE_EVIDENCE**. They are
  **not** production assets, are **not** approved/licensed, carry **no** production metadata,
  and are **not** served from a production CDN. Binaries + harness live in the git-ignored
  `evidence/fu-009/` working area; every number and SHA-256 is recorded below.

## 0. What this closes / does not close

- Provides **actual, browser-observed HTTP transfer** measurements over a **real local HTTP
  server** (no data URL, no base64 inline, no mocked size) for representative game-art-style
  images, across cold / cached / integrity-refetch / transient-retry paths.
- Does **not** confirm the budget: the canonical transfer target is a **bundle-level**
  `≤ 8 MiB` figure; a **per-asset** compressed-transfer sub-target is **neither defined nor
  required** by the canonical contract (§10) — **none is invented here**. Does **not** promote
  any budget to CONFIRMED, does **not** open the First Production Image Asset Gate, and is
  independent of FU-010 (hardware GPU).

## 1. Delivered set

7 images: **3 scene/reference** (full-frame app screenshots) + **4 standalone source**
overlays (HUD / effects). All 7 were read and measured.

## 2. Measurement method (honest basis)

- **Server:** local Node `http` server serving the staged PNGs. Routes: `/static/<f>`
  (`Cache-Control: public, max-age=300`, ETag) for cold+cached; `/nostore/<f>`
  (`Cache-Control: no-store`) for the integrity refetch; `/flaky/<f>` (first request → `503`
  empty body, then → `200` image) for transient retry. **No gzip / no content-encoding**
  applied — `decodedBodySize == encodedBodySize == file bytes` for every 200.
- **Client:** real **Chromium 131.0.6778.33** via Playwright 1.49.1, same-origin host page,
  reading `PerformanceResourceTiming` (`transferSize` = over-the-wire incl. response headers,
  `0` on memory-cache hit; `encodedBodySize` = response body bytes).
- **Env:** darwin arm64, Node v25.2.1, local loopback. `measured_at` 2026-08-12T01:54:24Z.
- Fetch cache modes mirror `ProductionImageAssetLoader`: normal load, then a `cache:'no-store'`
  integrity refetch; transient retry on `5xx`.
- **Boundaries (per canonical §25):** cold cache; **Content-Encoding = identity (recorded — no
  gzip/br)**; redirects: none; **Service Worker: none** (Playwright default, no SW registered);
  response **headers excluded** from the body figures below.

**Body vs wire — terminology (not conflated):** the tables report **response-body bytes**
(`encodedBodySize` from `PerformanceResourceTiming`). Over-the-wire `transferSize` was observed
as body **+ ~300 B** response headers for every 200, and ~300 B for a `503` (empty body). That
~300 B is an **`ESTIMATED_HTTP_OVERHEAD`** on loopback, **not** a precise wire-level capture; the
body figures are **not** presented as exact wire-transfer bytes.

## 3. File analysis — real alpha, not appearance (§2 / §12)

Alpha classification is taken from the **actual PNG alpha channel**, not visual appearance.
A baked-in checkerboard with `alpha==255` would be `OPAQUE`; only real `0..254` alpha is
`TRUE_ALPHA`.

| ID | File (raw) | Resolution | Mode | Alpha class | Opaque% | Partial% | Transparent% | Encoded | Decoded RGBA8 | Compress |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| S1 hud_dashboard | raw_1.png | 1536×1024 | RGBA | **TRUE_ALPHA** | 0.00 | 50.40 | 49.60 | 2,029,840 | 6,291,456 | 3.10× |
| S2 network_flow | raw_2.png | 1536×1024 | RGBA | **TRUE_ALPHA** | 0.00 | 27.53 | 72.47 | 1,496,123 | 6,291,456 | 4.21× |
| S3 fire_overload | raw_3.png | 1536×1024 | RGBA | **TRUE_ALPHA** | 0.00 | 40.29 | 59.71 | 1,839,464 | 6,291,456 | 3.42× |
| S4 portal_core | raw_4.png | 1536×1024 | RGBA | **TRUE_ALPHA** | 0.00 | 36.66 | 63.34 | 1,827,330 | 6,291,456 | 3.44× |
| C1 scene_campus_normal | raw_5.png | 1672×941 | RGB | **OPAQUE** (no alpha channel) | 100.00 | 0.00 | 0.00 | 2,857,142 | 6,293,408 | 2.20× |
| C2 scene_incident_heavy | raw_6.png | 1672×941 | RGB | **OPAQUE** | 100.00 | 0.00 | 0.00 | 2,938,159 | 6,293,408 | 2.14× |
| C3 scene_cloudscape | raw_7.png | 1672×941 | RGB | **OPAQUE** | 100.00 | 0.00 | 0.00 | 2,452,122 | 6,293,408 | 2.57× |

Findings:
- All 4 **standalone sources have genuine alpha** (`0..254` present); notably **0% fully-opaque**
  pixels — true anti-aliased/glow overlays, exactly the alpha-heavy runtime-texture case.
- All 3 **scenes have no alpha channel at all** → `OPAQUE`; they are **full-frame screenshots**,
  not individual production textures (see §7 caveat).
- Compression ratios 2.14×–4.21× are representative of real game-art complexity — **not** the
  pathological high-compression case of flat/solid or fully-transparent PNGs (§11).

SHA-256 (staged copies, unmodified):
```
S1 raw_1.png  71fb85500169aef6b1829e019de4b9e6f8e8e416352d0bf810570dff614bc8bd
S2 raw_2.png  45fadee8a0890dd31a11dc648b083adad439de0aefb8a61a3f510b63e5779f8e
S3 raw_3.png  186dd8c3deb44b7f14ca57c2b7931fe6cc6a1715e54a8523cb697bec8b390c2f
S4 raw_4.png  4c878a87ff8ebb57f1d2228052faa4e9f485e9c7e597c277bd2233a60c5c0557
C1 raw_5.png  155835e0c6e31ee19ad5da4a774f11462251d3a03884e3670ab081145f063c9d
C2 raw_6.png  60896551fd921dfabf8dfaa2ab1727d18059bdaffebe4e0cc30f9d82ba7b7e5f
C3 raw_7.png  0b3a668b7342550a0034cb65cea82369fd5f9babf78d507f703d81f66000936f
```

## 4. Sample classification (§3 / §20)

| ID | Role | Category | Runtime-like usage | Representative reason | Selected |
|---|---|---|---|---|---|
| S1 hud_dashboard | standalone source | **FLAT_UI_LIKE** (glow overlay) | HUD / dashboard / status panels | orange monitoring dashboard: panels, gauges, charts, status pills — flat UI regions with real alpha glow | YES |
| S2 network_flow | standalone source | **NETWORK_FLOW_EFFECT** | data-stream / network overlay | green data ribbons + nodes; 72% transparent, thin glowing lines — sparse-alpha network effect | YES |
| S3 fire_overload | standalone source | **ALPHA_HEAVY_EFFECT** | fire / particle overlay | standalone flame + embers + smoke; 60% transparent, alpha-heavy edges | YES |
| S4 portal_core | standalone source | **GLOW_PARTICLE_EFFECT** | portal / energy overlay | blue sync-core: radial glow, particles, circuit fragments — glow/particle effect | YES |
| C1 scene_campus_normal | full scene | **DETAILED_BUILDING_ENVIRONMENT** | detailed-art / full-frame reference | server buildings, campus, characters, roads, UI overlays — high spatial+color complexity | YES |
| C2 scene_incident_heavy | full scene | **EFFECT_HEAVY_SCENE** | effect-heavy full-frame reference | full scene + fire, warning layers, data flows, holographic overlays | YES |
| C3 scene_cloudscape | full scene | **DETAILED_BUILDING_ENVIRONMENT** (simpler) + UI | detailed-art / UI+environment reference | tech-park scene: buildings, characters, panels — detailed but flatter than C1 | YES |

## 5. Final measurement set & coverage (§5 / §21)

All 7 measured; per-characteristic representative (results reported **separately per
characteristic — not averaged across characteristics**, §5):

- **FLAT_UI_LIKE** → S1 hud_dashboard
- **DETAILED_BUILDING_ENVIRONMENT** → C1 scene_campus_normal (also C3 scene_cloudscape)
- **EFFECT / ALPHA-LIKE** → S3 fire_overload (standalone) ; C2 scene_incident_heavy (in-scene)
- **NETWORK_FLOW_EFFECT** → S2 network_flow
- **GLOW_PARTICLE_EFFECT** → S4 portal_core

Minimum 3-characteristic coverage: **satisfied** (FLAT_UI + DETAILED + EFFECT/ALPHA), plus
NETWORK_FLOW and GLOW_PARTICLE. Standalone-source priority (HUD / fire / data-stream / portal,
§6) all included. None of the 4 sources are opaque, so none is reclassified to
`OPAQUE_EFFECT_REFERENCE`.

## 6. Transfer evidence (§10 / §13 / §22) — response-body bytes (`encodedBodySize`)

| Sample | Category | Resolution | Encoded | Alpha | Cold body | Cached body | Integrity refetch (total body) | Retry (total body) | Repr. |
|---|---|---:|---:|---|---:|---:|---:|---:|---|
| S1 hud_dashboard | FLAT_UI_LIKE | 1536×1024 | 2,029,840 | TRUE_ALPHA | 2,029,840 | **0** (cache hit) | 4,059,680 | 2,029,840 | YES |
| S2 network_flow | NETWORK_FLOW_EFFECT | 1536×1024 | 1,496,123 | TRUE_ALPHA | 1,496,123 | **0** | 2,992,246 | 1,496,123 | YES |
| S3 fire_overload | ALPHA_HEAVY_EFFECT | 1536×1024 | 1,839,464 | TRUE_ALPHA | 1,839,464 | **0** | 3,678,928 | 1,839,464 | YES |
| S4 portal_core | GLOW_PARTICLE_EFFECT | 1536×1024 | 1,827,330 | TRUE_ALPHA | 1,827,330 | **0** | 3,654,660 | 1,827,330 | YES |
| C1 scene_campus_normal | DETAILED_BUILDING_ENVIRONMENT | 1672×941 | 2,857,142 | OPAQUE | 2,857,142 | **0** | 5,714,284 | 2,857,142 | YES |
| C2 scene_incident_heavy | EFFECT_HEAVY_SCENE | 1672×941 | 2,938,159 | OPAQUE | 2,938,159 | **0** | 5,876,318 | 2,938,159 | YES |
| C3 scene_cloudscape | DETAILED_BUILDING_ENVIRONMENT | 1672×941 | 2,452,122 | OPAQUE | 2,452,122 | **0** | 4,904,244 | 2,452,122 | YES |

Transfer basis, kept distinct — **never summed into one number** (§10 / §11):
- **ENCODED_SOURCE_BYTES** = on-disk PNG bytes (= Encoded column).
- **COLD_HTTP_BODY_BYTES** = cache-miss response body (= Cold body column). Equals encoded
  bytes here (identity encoding).
- **CACHED_HTTP_BODY_BYTES** = `0` — `max-age` cache hit; `encodedBodySize`/`transferSize == 0`,
  i.e. **no response body re-transferred and no network fetch observed** for the fresh hit.
  Reported as `CACHE_BODY_TRANSFER = 0`, **not** claimed as "an HTTP layer that can never issue
  a request."
- **INTEGRITY_REFETCH_BODY_BYTES** = normal fetch + `cache:'no-store'` refetch = **2× body**.
- **TRANSIENT_RETRY_BODY_BYTES** = `503` (0 body) + one successful `200` = **1× body**. On the
  wire the `503` still carries headers, so `RETRY_TOTAL_WIRE_BYTES > RETRY_TOTAL_BODY_BYTES`;
  they are **not** equated.
- **ESTIMATED_HTTP_OVERHEAD** ≈ 300 B/response (loopback estimate, not a wire capture).

### Per-characteristic summary (separate, not cross-averaged)
- **FLAT_UI_LIKE** (S1): cold 1.94 MiB; integrity 3.87 MiB; retry 1.94 MiB.
- **DETAILED_BUILDING_ENVIRONMENT** (C1 / C3): cold 2.72 / 2.34 MiB — reported individually.
- **EFFECT_HEAVY_SCENE** (C2): cold 2.80 MiB (largest single sample).
- **ALPHA_HEAVY_EFFECT** (S3): cold 1.75 MiB.
- **NETWORK_FLOW_EFFECT** (S2): cold 1.43 MiB (smallest; 72% transparent).
- **GLOW_PARTICLE_EFFECT** (S4): cold 1.74 MiB.

## 7. Scene-vs-source caveat (§7)

Scene samples (C1/C2/C3) are **full-frame app screenshots**, not individual production textures
consumed by `ProductionImageAssetLoader`. They are used as **detailed-art encoded-size /
high-entropy full-frame / UI+environment composition** references only. **Do not** treat
"scene screenshot == production texture workload." Standalone sources (S1–S4) are the
closer-to-runtime overlays. Reported separately above.

## 8. Budget target linkage (§14)

Canonical target: `visual-asset-budget.md` → **"Compressed transfer size target: ≤ 8 MiB"**
(`core.CRITICAL_TRANSFER_BYTES = 8·1024·1024`). This is a **bundle-level** ("initial critical
bundle") compressed-transfer ceiling, and it is a compressed/encoded figure — matching
COLD_HTTP_TRANSFER_BYTES.

| Sample | Cold (MiB) | % of 8 MiB bundle ceiling | Single-asset headroom | Verdict |
|---|---:|---:|---:|---|
| S1 | 1.94 | 24.2% | 6.06 MiB | within (single) |
| S2 | 1.43 | 17.8% | 6.57 MiB | within (single) |
| S3 | 1.75 | 21.9% | 6.25 MiB | within (single) |
| S4 | 1.74 | 21.8% | 6.26 MiB | within (single) |
| C1 | 2.72 | 34.1% | 5.28 MiB | within (single) |
| C2 | 2.80 | 35.0% | 5.20 MiB | within (single) |
| C3 | 2.34 | 29.2% | 5.66 MiB | within (single) |

Honest verdict: **every single sample is < 8 MiB**, but the target governs the **whole critical
bundle**, not one asset. At ~2.8 MiB each, three such images would exceed the 8 MiB bundle
budget, and an integrity-refetch path already spends up to 5.60 MiB (70% of the bundle budget)
on one asset — these are **worst-case illustrations, not real bundle failures**. A **per-asset
sub-target is not defined and is not required** by the canonical contract (§10); the per-asset
PASS/FAIL is therefore **N/A** (no number invented). Bundle-level PASS/FAIL is
`FIRST_PRODUCTION_BUNDLE_EVALUATION_PENDING` — composition-dependent, decided only on a real
included set.

## 9. Production boundary (§16)

- Production Asset: **NONE** · Production Metadata: **NONE** · Production CDN: **NONE**
- Production Approval: **NONE** · Production License Record: **NONE**
- These 7 files = **NON_PRODUCTION_REPRESENTATIVE_EVIDENCE**, stored in git-ignored
  `evidence/fu-009/` (never in the production runtime bundle).

## 10. Canonical §25 completion-contract reconciliation

The canonical FU-009 completion contract (`production-asset-budget-confirmation.md §6`) reads
**DONE when** "one measurement tool + fixed boundaries are specified **and C17 aligns to them**".
The DONE condition is about **specifying the measurement system and aligning it to C17** — it does
**not** require evaluating a real production included set (that is the downstream Gate step).
Reconciled against that exact condition:

| Canonical DONE element | This evidence | State |
|---|---|---|
| One measurement tool **specified** | real Node HTTP server + Playwright Chromium 131 + `PerformanceResourceTiming` | **MET** |
| Fixed boundaries **specified** | cold cache; Content-Encoding recorded (identity here); redirects excluded; SW recorded (none); headers excluded; bundle-inclusion scope defined = **image binaries + manifest JSON + atlas JSON** | **MET** |
| Actual HTTP download bytes, cold cache | measured per sample (Cold body column) | **MET** |
| **C17 aligns** to the measured transfer (relationship + allowed delta defined) | defined below — C17 static is a **conservative upper bound** of browser cold transfer | **MET** |

**C17 alignment (finalized, no number invented):** C17 (`checks.py::c17_bundle_size`) sums the
**on-disk artifact bytes** of a critical bundle vs `CRITICAL_TRANSFER_BYTES` (8 MiB). The
relationship to the browser cold transfer is:

> **`C17_static_bytes ≥ browser_COLD_HTTP_BODY_BYTES`** — C17 is a **conservative upper bound**.

- For **image binaries** (identity Content-Encoding): browser body **equals** on-disk bytes
  exactly (proven: `decodedBodySize == encodedBodySize == file bytes`) → **delta ≈ 0** (headers
  excluded, which C17 also excludes).
- For **manifest/atlas JSON** under gzip/br: browser transfer **≤** on-disk (compressible) →
  C17 **over-estimates**, delta ≥ 0.

So the **allowed delta** is `0 ≤ (C17_static − browser_transfer) ≤ header_overhead +
JSON_compression_savings`, with C17 never under-counting. C17 is therefore a **safe static gate**
for the browser-measured transfer. This defines the relationship + allowed delta the contract
asks for — **without a per-asset target and without a new budget number.**

## 11. Status

- **POLICY-C-FU-009: `COMPLETE`** (Case A). The canonical DONE condition is met:
  `MEASUREMENT_TOOL_SPECIFIED` + `FIXED_BOUNDARIES_SPECIFIED` + `TRANSFER_BASIS_DEFINED` +
  `REPRESENTATIVE_MEASUREMENT_COMPLETE` + `C17_ALIGNMENT_DEFINED` (C17 = conservative upper
  bound). The representative measurement validated the measurement **system**; the contract does
  **not** require measuring a real assembled production bundle.
- **`FIRST_PRODUCTION_BUNDLE_TRANSFER_EVALUATION: PENDING_FIRST_PRODUCTION_INCLUDED_SET`** — the
  actual ≤ 8 MiB verdict on a **real** included set (image binaries + manifest JSON + atlas JSON)
  is evaluated **downstream at the First Production Image Asset Gate / C17** when a production
  candidate exists. `PRODUCTION_BUNDLE_COMPOSITION: NOT_YET_DEFINED`. Single-asset "< 8 MiB" is
  **not** a `BUNDLE_PASS`; "3 scenes > 8 MiB" is only a worst-case illustration, **not** a real
  failure.
- **`PER_ASSET_TRANSFER_TARGET: NOT_DEFINED`** — and **not required** by the canonical contract;
  **no per-asset number is invented** here.
- **8 MiB target unit reconfirmed:** `core.CRITICAL_TRANSFER_BYTES` is
  `BUNDLE_LEVEL_COMPRESSED_TRANSFER` (C17 sums a whole critical bundle), **not** a per-asset target.
- Unchanged: Budget = `PROPOSED_TARGETS_WITH_GAPS`; First Production Image Technical Readiness =
  `NOT_READY`; First Production Image Asset Gate = **CLOSED**. Related tracks:
  **FU-008 = `COMPLETE_IN_DEV`**, **FU-010 = `COMPLETE_IN_DEV`** (hardware-GPU track closed).
- No product code changed; no production contamination.

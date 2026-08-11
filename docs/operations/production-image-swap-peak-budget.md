# Production Image Swap-Peak Budget (BUDGET-POLICY-FU-001)

- Owner: Program/Policy · Status: **POLICY-C-FU-008: POLICY_DEFINED_PENDING_MEASUREMENT**
- Base: dev `a5719a2`. **Policy/docs only — no product code, no production asset.**
- Removes the `(to define)` swap-peak entry from `production-asset-budget-confirmation.md
  §2/§5`. **No new unrelated budget number is introduced** — the peak reuses the existing
  resident/critical targets from `visual-asset-budget.md`. Nothing is promoted to CONFIRMED
  (the number stays PROPOSED until measured under FU-008 + DevCTO sign-off).

## 1. What "swap peak" is

Per the FU-008 completion contract, three quantities are distinguished during a manifest /
texture-version replacement (see `AssetManager.replaceManifest` + versioned cache):

- `steady_state_gpu_memory` — resident texture bytes before the swap.
- `manifest_swap_peak_gpu_memory` — resident bytes at the moment the **old (v1)** and
  **new (v2)** versions coexist (v1 handles still held while v2 is Ready).
- `post_cleanup_gpu_memory` — resident bytes after v1 handles are released and stale
  cleanup has run.

The measured quantity of record is:

```
manifest_swap_peak_gpu_memory
  = Σ resident_texture_bytes( every texture alive during the v1→v2 transition )
  = steady_state( assets NOT being swapped )
    + Σ ( OLD_version_bytes + NEW_version_bytes )  for each swapped asset
```

Bytes are the canonical estimate `core.gpu_bytes` (RGBA8 = `w·h·4`), **mipmapped bytes
included** (`·4/3`) for any texture that opted into mipmaps.

## 2. Chosen policy form

**Form C — `OLD_PLUS_NEW_RESIDENT_COEXISTENCE`** (old+new per-asset, aggregated to a
bundle-level peak), bounded by the **existing resident target**. Rationale:

- The resident target (64 MiB) is the *physical device ceiling*; exceeding it — even
  transiently during a swap — risks allocation failure / WebGL context loss. So the ceiling
  must apply to the **peak**, not only steady-state.
- This reuses a number already of record. It does **not** introduce a separate absolute
  swap number (Form A) or an invented multiplier (Form B). The "multiplier" is emergent, not
  authored: a full-coexistence swap of a bundle approaches ~2× its steady-state, which the
  64 MiB ceiling then constrains.

## 3. The budget (PROPOSED — reuses existing targets)

| Item | Value (PROPOSED, reused) |
|---|---|
| `swap_peak_budget_basis` | `OLD_PLUS_NEW_RESIDENT_COEXISTENCE` (mipmapped bytes included) |
| `swap_peak_limit` (resident) | ≤ **64 MiB** — the existing total-resident target applies to the peak |
| `swap_peak_limit` (critical set) | critical steady-state target (**32 MiB**) is unchanged; a critical-set swap's peak still must fit the **64 MiB** resident ceiling |
| mipmapped bytes | **included** in old and new |
| `post_cleanup` condition | `post_cleanup_gpu_memory == steady_state( new manifest )` — every superseded version released + stale-collected; no residual old-version texture |
| temporary coexistence allowed | only while `manifest_swap_peak_gpu_memory ≤ 64 MiB`; larger swaps must be **staged** (release-before-load per asset) so the peak never exceeds the ceiling |

No load-time/transfer number is changed here; this policy governs the **resident GPU peak**
during replacement only.

## 4. 4096² relationship (reinforces the exception)

A single 4096² RGBA8 texture is **64 MiB decoded = the entire resident ceiling** (mipmapped
≈ 85.33 MiB, already over it). Therefore a 4096² asset **cannot be hot-swapped within the
resident budget** (old 64 + new 64 = 128 MiB peak ≫ 64 MiB). Consequences:

- 4096² remains **exception-only** (FU-007). This policy does **not** relax it to a general
  allowance.
- A permitted 4096² swap must use a **release-before-load (non-coexisting)** path — accept a
  brief fallback rather than v1+v2 coexistence — and still requires the DevCTO dimension
  exception. Coexisting 4096² swaps are **denied**.

## 5. Exception authority

Swap-peak overage (a bundle whose swap peak would exceed 64 MiB) is waivable **only** by a
**DevCTO exception record** (same authority + record shape as the dimension/budget exception
in `production-asset-approval-workflow.md §5`), bound to `asset_id + asset_version`, and
reconciled against the whole resident budget (one asset's exception may not push the bundle
peak over resident).

## 6. CI enforcement feasibility

- The **true** peak is a *runtime* quantity (v1+v2 coexistence during `replaceManifest`) and
  must be measured under FU-008 in a hardware-GPU reference env (BUDGET-ENV-FU-003).
- A **conservative static upper bound** is computable at build time and could be enforced
  by the validator (C18-adjacent): `worst_case_swap_peak ≈ steady_state_resident +
  max_single_new_version_resident ≤ 64 MiB`. This is a safe over-estimate suitable for a CI
  gate. **Not implemented in this policy PR** — tracked as **P4-BUDGET-FU-001**
  (`BLOCKED_BY_BUDGET_CONFIRMATION`); it is enabled only after the number is CONFIRMED.

## 7. Validator / dry-run input contract

FU-008 measurement (and any future static check) consumes, per asset: `assetVersion`,
`pixel_width`, `pixel_height`, `mipmap` flag, `bundleId`, and the old→new version pair being
swapped. The runtime already exposes the swap lifecycle (`replaceManifest` → stale →
`disposeStale`); the P4 harness observes it. The dry-run peak is derived from
`core.gpu_bytes` over the coexisting set.

## 8. Status

- **POLICY-C-FU-008: `POLICY_DEFINED_PENDING_MEASUREMENT`.** The basis, limit (reused 64 MiB
  resident), mipmap inclusion, post-cleanup condition, 4096² relationship, exception
  authority, CI feasibility, and input contract are defined. **Not COMPLETE** — the number
  stays PROPOSED until:
  1. measured against the procedure in a hardware-GPU reference env (BUDGET-ENV-FU-003), and
  2. reviewed (Ops+Frontend) then **DevCTO-signed** (MEASURED→REVIEWED→CONFIRMED).
- First Production Image Asset Gate remains **CLOSED**. No production asset added.

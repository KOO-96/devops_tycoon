# Visual Asset Budget (ASSET-OPS-002)

- Owner: Infra/Platform · Status: **ASSET-OPS-002: REVIEW_PENDING**
- Base: dev `65adf13`. All numbers below are **Proposed** — not Confirmed until
  reviewed. Documentation only.

> **Budget confirmation (P1):** the per-item `PROPOSED → MEASURED → REVIEWED → CONFIRMED`
> workflow and the POLICY-C-FU-006~010 completion contracts (mipmap, 4096² exception,
> swap-peak, transfer basis, reference environment) are in
> [`production-asset-budget-confirmation.md`](./production-asset-budget-confirmation.md).
> These numbers remain **PROPOSED**; P1 promotes nothing to Confirmed/SLA.

Numeric budgets for textures, atlases, memory, loading, and animation, sized for the
Illustrated Pixel Hybrid direction (UI-D-001) on the 128×64 logical / 64×32 source /
2× integer scale (UI-D-002).

## Texture & atlas (Proposed)

| Item | Recommended | Hard max |
|---|---|---|
| Single texture | 2048×2048 | 4096×4096 |
| Atlas | 2048×2048 | 4096×4096 |

- **NPOT:** allowed for standalone images; atlases SHOULD be power-of-two. Padding
  between atlas frames ≥ **2px**; edge **extrusion ≥ 1px** to prevent bleeding.

## Initial critical bundle (Proposed)

- Critical atlases at startup: **≤ 2**
- Compressed transfer size target: **≤ 8 MiB**
- Estimated GPU texture memory target: **≤ 32 MiB**
- Visual MVP total resident texture target: **≤ 64 MiB**

**Memory estimate (RGBA8):** `width × height × 4 bytes` per texture (e.g. a
2048×2048 RGBA8 texture ≈ 16 MiB). If MipMaps are enabled, add ~33% per texture
(`× 1.333`). Budgets above assume no mipmaps unless a texture opts in.

## Loading (Proposed; reference env)

Reference environment: mid-range laptop, wired/typical broadband, warm Vite dev or
production static hosting. Targets:

- Initial critical-asset cold load: **≤ 4 s**
- Warm-cache load: **≤ 1.5 s**
- Single bundle timeout: **8 s**
- Auto retry: **≤ 2**, backoff **250ms → 750ms**
- After retries exhausted → **fallback**

## Animation (Proposed)

- Concurrent AnimatedSprite: **≤ 48**
- Concurrent request-flow markers: **≤ 128**
- Concurrent particles: **≤ 256**
- Off-screen AnimatedSprite: pause or low-frequency update
- Reduced motion: minimize looping pulse/particles
- **No per-frame full building sort** (depth sort only on structural/position change
  — matches the PR B depth policy)

## Scene complexity (Proposed)

- Functional nodes: verified at **≥ 50** (PR B smoke already meets this)
- Interactive objects: functional nodes only; decorative `interactive = false`
- Shared fallback texture reused (never one texture per node)

## Exception policy

Exceeding a Hard Max requires: reason, alternatives considered, memory estimate,
loading impact, low-end impact, approver, and an expiry/re-review date. **No merge
without DevCTO (or a designated ops) approval.**

## Status
**ASSET-OPS-002: REVIEW_PENDING** — Proposed numbers, not Confirmed.

# Production Asset Budget Confirmation & FU-006~010 Completion (P1)

- Owner: Program (process) / Ops (measurement) / Frontend (instrumentation) · Status:
  **P1: POLICY_DEFINED_PENDING_DEVCTO_REVIEW**
- Policy only. Defines the budget confirmation workflow and the **completion contracts**
  for POLICY-C-FU-006~010. **Does NOT promote any number to Confirmed/SLA** — budgets remain
  **PROPOSED TARGETS**. Numbers of record stay in `visual-asset-budget.md`.

## 1. Budget state model (§20) — per item

```
PROPOSED  →  MEASURED  →  REVIEWED  →  CONFIRMED
```

Each transition requires:

| Transition | Requires |
|---|---|
| PROPOSED → MEASURED | reference environment (FU-010), fixture/asset set, repeat count, documented method, recorded results |
| MEASURED → REVIEWED | Ops + Frontend review of the measurement; anomalies explained |
| REVIEWED → CONFIRMED | DevCTO sign-off; exception policy for overages recorded; result location fixed |

- **Budgets are managed and confirmed PER ITEM**, not all-at-once. A CONFIRMED item still
  has an exception path (`production-asset-approval-workflow.md §5`).
- **P1 promotes nothing.** All items remain `PROPOSED`.

## 2. Per-item budget identity (§21)

Each is tracked with its own state; Request-Flow/Particle caps existing here **does not**
imply EVENT_DERIVED approval (POLICY-C-FU-002 remains NOT_IMPLEMENTED).

| Budget item | Current (Proposed) | State |
|---|---|---|
| Texture recommended dimension | 2048×2048 | PROPOSED |
| Texture hard max | 4096×4096 (exception only) | PROPOSED |
| Atlas dimension | 2048² rec / 4096² max; pad ≥2px; extrude ≥1px | PROPOSED |
| Critical atlas count | ≤ 2 | PROPOSED |
| Critical transfer bytes | ≤ 8 MiB | PROPOSED |
| Critical GPU memory | ≤ 32 MiB | PROPOSED |
| Total resident GPU memory | ≤ 64 MiB | PROPOSED |
| Cold load time | ≤ 4 s | PROPOSED |
| Warm load time | ≤ 1.5 s | PROPOSED |
| Attempt timeout | 8 s | PROPOSED |
| Animated sprite count | ≤ 48 | PROPOSED |
| Flow marker count | ≤ 128 | PROPOSED |
| Particle count | ≤ 256 | PROPOSED |
| Manifest swap peak | (to define, FU-008) | PROPOSED |

## 3. FU-006 — Mipmap budget (completion contract, §22)

- The 32 MiB critical GPU target assumes **no mipmaps**. A mipmap opt-in recomputes the
  estimate; the asset must still satisfy the budget or an approved exception.
- **GPU memory formula (contract for the validator, not implemented here):**
  `bytes = pixel_width × pixel_height × channels × bytes_per_channel × compression_factor`;
  RGBA8 = 4 B/px; mipmaps add ≈ ×1.333 (full chain). Atlas counts its full image dimensions.
- Validator input includes a `mipmap` flag per asset; C18 uses it.
- **DONE when:** the formula + inputs are specified and C18 evaluates mipmap vs no-mipmap
  and enforces the budget/exception. (P1 = contract only.)

## 4. FU-007 — Oversized 4096² exception (completion contract, §23)

- 4096² is a **hard-max exception**, not a general allowance. Requires a DevCTO exception
  record (fields per `production-asset-approval-workflow.md §5`): `exception_id`,
  `asset_id`, `asset_version`, `requested_dimension`, `estimated_gpu_memory`,
  `resident_budget_impact`, `justification`, `alternatives_considered`, `approved_by`
  (DevCTO), `approved_at`, `expires_at`/`review_at`, `status`.
- Reconciled against the **64 MiB resident** budget **together with all other resident
  textures** — one asset's exception may not push the bundle over resident. Re-approved on
  `asset_version` change.
- **DONE when:** C15/C16 honor a validated exception and C18 sums the exception into the
  resident total.

## 5. FU-008 — Swap-peak budget (completion contract, §24)

Distinguish three quantities:
`steady_state_gpu_memory`, `manifest_swap_peak_gpu_memory`, `post_cleanup_gpu_memory`.

Measurement procedure: (1) manifest v1 Ready → record steady; (2) start v2 load with v1
handles retained; (3) v2 Ready → record **peak** (v1+v2 coexist); (4) release v1 handles;
(5) stale cleanup; (6) record post-cleanup steady.

- **DONE when:** the method is documented, an allowed peak bound is set (number stays
  Proposed until CONFIRMED), the "post-cleanup returns to steady" condition is defined, and
  the validator/dry-run input contract is fixed. (No number confirmed in P1.)

## 6. FU-009 — Transfer measurement basis (completion contract, §25)

- Critical bundle transfer = **actual HTTP download bytes**, cold cache, after
  `Content-Encoding` compression (encoding recorded); includes required image binaries +
  atlas JSON + manifest JSON; excludes redirects/headers; Service-Worker cache disabled or
  its state recorded.
- Define the relationship between the validator **static** size check (C17) and the
  **browser-measured** transfer, and the allowed delta between them.
- **DONE when:** one measurement tool + fixed boundaries are specified and C17 aligns to them.

## 7. FU-010 — Reference environment (completion contract, §26)

Required record: OS; browser + version; CPU; GPU/renderer; **hardware vs software renderer**;
RAM; network profile; cache state; device pixel ratio; viewport; build mode; runtime
manifest version; bundle version.

Timing: **start = manifest request**; **end = critical asset Ready incl. decode + GPU
upload**.

- **SwiftShader (software) evidence is NOT a hardware-GPU result** and must be labeled as
  software; hardware-GPU verification is a separate follow-up.
- **DONE when:** the reference-environment spec + a measurement template + a result-record
  format exist and each load budget number is stated **against a named environment**.

## Status
Budget confirmation workflow + FU-006~010 completion contracts defined. **Budgets remain
PROPOSED TARGETS.** No number promoted. FU-005~010: `POLICY_DEFINED_IMPLEMENTATION_PENDING`.

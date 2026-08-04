# First Production Asset Gate (P1 — definition only)

- Owner: DevCTO (final sign-off) / Program (definition) · Status: **First Production Asset
  Gate: CLOSED**
- Policy only. Defines the pass procedure for merging the **first real production asset**.
  **No asset is approved in P1.** The gate stays CLOSED until every condition below is met.
- Companions: [`production-asset-metadata-policy.md`](./production-asset-metadata-policy.md),
  [`production-asset-approval-workflow.md`](./production-asset-approval-workflow.md),
  [`asset-ops-004-contract-matrix.md`](./asset-ops-004-contract-matrix.md),
  [`production-asset-budget-confirmation.md`](./production-asset-budget-confirmation.md).

## Gate checklist (§30)

A production asset may merge **only when ALL** hold:

1. **ASSET-OPS-004 required check green** on the asset (status `REQUIRED_CHECK_ENFORCED`+).
2. **POLICY-C-FU-005~010 complete** (`IMPLEMENTED`, per their completion contracts).
3. Metadata **schema valid** (C01).
4. `approval_state == APPROVED_FOR_PRODUCTION` + `production_approved == true`, bound to the
   asset's `asset_version` (C14).
5. `license_type != unknown` with satisfied evidence (C13).
6. `approved_by` + `approved_at` present (C14).
7. Human review complete (`source_provenance.human_reviewed == true`).
8. **No reference reproduction** (`reference_usage` is a bounded study category, not
   reproduction).
9. `checksum_sha256` matches the binary (C12).
10. Texture dimension passes **or** valid DevCTO exception (C15/FU-007).
11. Atlas checks pass (C05/C06/C16).
12. Bundle size within budget (C17/FU-009).
13. GPU memory within budget incl. mipmap/4096² accounting (C18/FU-006/FU-007).
14. Fallback exists, no cycle, depth ≤ 3 (C09/C10/C11).
15. Deterministic manifest regenerated with **zero diff** vs committed (C22).
16. **Binary + Metadata + Manifest changed atomically** in one PR (§atomicity).
17. `build_id` consistent (C24).
18. Rollback artifact present (C25).
19. **DevCTO sign-off** recorded.
20. Budget items **CONFIRMED to the level the asset requires** (the specific items the asset
    exercises must be `CONFIRMED`, per `production-asset-budget-confirmation.md`; unrelated
    items may remain Proposed).

## Ordering / dependencies

- The gate cannot open until **P2 (validator + required CI check)** and **P3 (deterministic
  generator)** are complete and **P4 (end-to-end dry-run with a throwaway placeholder)** has
  proven the whole path green — all **without** a committed binary.
- Rights/approval conditions (4–9, 19) are **never** waivable by exception; only the
  technical budget/dimension checks (10, 12, 13) may use a DevCTO exception record.

## What P1 does NOT do

Does not approve any asset, add any binary/sprite/atlas/font, promote any budget to
Confirmed/SLA, implement the validator/generator/CI, or open the gate. The gate remains
**CLOSED**.

## Status
Gate **defined**, **CLOSED**. Opens only after P2/P3/P4 complete and the checklist passes
for a specific asset with DevCTO sign-off.

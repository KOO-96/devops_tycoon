# Production Asset Approval & Exception Workflow (P1)

- Owner: Program · Status: **P1: POLICY_DEFINED_PENDING_DEVCTO_REVIEW**
- Policy only. Governs the approval state machine, the approval record, the
  inclusion/exclusion logic the generator obeys, and the DevCTO exception procedure.
  Companion to [`production-asset-metadata-policy.md`](./production-asset-metadata-policy.md).

## 1. Approval state model (§10)

`approval_state` enum (a single boolean cannot express the workflow):

```
DRAFT
RIGHTS_REVIEW_REQUIRED
RIGHTS_REJECTED
TECHNICAL_REVIEW_REQUIRED
TECHNICAL_REJECTED
APPROVED_FOR_PRODUCTION
DEPRECATED
REVOKED
```

Transitions (happy path): `DRAFT → RIGHTS_REVIEW_REQUIRED → TECHNICAL_REVIEW_REQUIRED →
APPROVED_FOR_PRODUCTION`. Rejections branch to `RIGHTS_REJECTED` / `TECHNICAL_REJECTED`.
Post-approval: `→ DEPRECATED` (superseded, kept for rollback) or `→ REVOKED` (rights/policy
withdrawal).

- **The ONLY state the generator may include in a production manifest is
  `APPROVED_FOR_PRODUCTION`** (and only with all §3 gates true).
- **`DEPRECATED`**: not included in a **new** manifest; existing releases may still
  reference it for rollback.
- **`REVOKED`**: never included in any new manifest; flagged for rollback review — a
  release still pointing at a revoked asset must be re-cut. `DEPRECATED ≠ REVOKED`.
- **`production_approved` (existing ASSET-OPS-001 boolean) is retained but SUBORDINATE**:
  it must be `true` **iff** `approval_state == APPROVED_FOR_PRODUCTION`. A mismatch
  (`production_approved=true` with any other state, or vice-versa) is a hard error.

## 2. Approval record (§11)

Required on `APPROVED_FOR_PRODUCTION`:

```
approval:
  approval_state: APPROVED_FOR_PRODUCTION
  reviewed_asset_version:   # the asset_version this approval is bound to
  approval_scope:           # e.g. "production" — fixed to the reviewed version
  approved_by:              # person/org identity (not a secret)
  approved_at:              # UTC ISO-8601
  rights_review_reference:  # audit reference to the rights review
  technical_review_reference:
  review_notes:             # or an internal review reference
```

- **Approval is bound to `reviewed_asset_version`.** A new `asset_version` does **not**
  inherit approval — it re-enters `TECHNICAL_REVIEW_REQUIRED` (and `RIGHTS_REVIEW` if the
  source/license changed).
- `production_approved=true` **without** a complete approval record is a hard error.
- Approval records live under `assets/approvals/`; **never** copied into the runtime
  manifest, and contain **no PII/secrets** beyond the recorded approver identity.

## 3. Production inclusion rule (§14)

The generator includes an asset in the production runtime manifest **iff all** hold:

```
include(asset) =
      schema_valid
  AND approval_state == APPROVED_FOR_PRODUCTION
  AND production_approved == true
  AND approval bound to the asset's current asset_version
  AND license_type != unknown  AND license evidence satisfied
  AND approved_by present  AND approved_at present
  AND checksum_sha256 present and valid (verified against the binary)
  AND technical constraints pass (dimension / atlas / fallback / budget-or-approved-exception)
  AND approval_state not in { DEPRECATED, REVOKED }
```

Any single failure ⇒ **excluded**, via a validator failure or an explicit exclusion
report entry. **Silent inclusion is prohibited.**

## 4. Exclusion / severity policy (§15)

| Condition | CI outcome |
|---|---|
| `license_type == unknown` | **HARD ERROR — merge blocked** |
| `production_approved == false` (or no approval record) | **HARD ERROR — merge blocked** |
| `approval_state == REVOKED` in a new manifest input | **HARD ERROR — merge blocked** |
| `approval_state == DRAFT / *_REVIEW_REQUIRED / *_REJECTED` in production generation input | **HARD ERROR — merge blocked** |
| schema invalid / checksum mismatch / fallback cycle / deterministic-gen failure / missing rollback artifact | **HARD ERROR — merge blocked** |
| `approval_state == DEPRECATED` | **Excluded with report** (not an error; kept for rollback) |
| Non-blocking advisory (e.g. unused optional field) | **Warning** |

### 4a. Exclusion report — minimum contract (§23)

Every excluded asset gets a report entry (no silent exclusion):

```
{ asset_id, asset_version, approval_state, exclusion_reason_code, source_metadata_path,
  referenced_by_runtime: bool, merge_blocking: bool, message }
```

- `DEPRECATED` **must** appear in the exclusion report.
- If an excluded asset is `referenced_by_runtime`, the `unmanifested runtime asset` check
  (C20) **fails** (merge-blocked) — an excluded-but-needed asset never silently disappears.
- `REVOKED` is excluded from new manifests **and** hard-errors on new input, **and** is
  subject to rollback-eligibility (§5a).

### 5a. REVOKED must not be reactivated by rollback (§22)

A rollback artifact may **record** past releases that referenced a now-`REVOKED` asset
(history/audit), but the pipeline **prohibits**: a current rollback **candidate** that
reactivates a REVOKED asset; a rollback index marking a REVOKED-containing release
`eligible=true`; any new release including a rights-revoked asset. **C25 is extended**:
every asset in a rollback candidate manifest is checked against current approval state; a
candidate containing a REVOKED asset is **ineligible** (`ASSET_ROLLBACK_REVOKED_TARGET`),
and if **no** safe (no-REVOKED) rollback artifact exists the release gate **fails**.
**Never exceptionable — not even by DevCTO;** a re-cut or a safe rollback artifact is
required.

## 5. Exception procedure (§29)

Some technical checks may be waived by a **DevCTO-signed exception**; rights/approval
checks may **never** be waived.

**Exception-allowed (technical):** 4096² dimension (POLICY-C-FU-007), a specific budget
overage, a bounded temporary stale-retention, a specific bundle structure.

**Never exceptionable:** `license_type == unknown`; missing production approval; checksum
mismatch; fallback cycle; schema invalid; deterministic-generation failure; missing
rollback artifact.

Exception record (under `assets/approvals/exceptions/`):

```
exception:
  exception_id:
  asset_id:  asset_version:            # bound to a specific version
  check_id:                            # the ASSET-OPS-004 check being waived
  requested_value:  budget_impact:     # e.g. dimension + estimated GPU memory + resident impact
  justification:  alternatives_considered:
  approved_by: DevCTO                  # approver fixed to DevCTO
  approved_at:  expires_at | review_at:
  status: active | expired | revoked
```

- Approver is **fixed to DevCTO**. Bound to a specific `asset_id + asset_version`;
  changing the version **re-requires** approval. Auto-expires / requires re-review.
- CI **verifies the exception record** (present, active, unexpired, matches the asset and
  check) before treating a check as waived; a waiver without a valid record is a hard error.
- One asset's exception may **not** authorize a whole-bundle budget overage (§budget
  reconciliation, `production-asset-budget-confirmation.md`).

## Status
P1 defined; not implemented. `ASSET-OPS-004`: **POLICY_DEFINED_IMPLEMENTATION_PENDING**.

# ASSET-OPS-004 — Production Asset Validator (Operation & Enforcement)

- Owner: Ops (implementation) / Program (policy) · Status:
  **ASSET-OPS-004: IMPLEMENTED_PENDING_CI_ENFORCEMENT**
- Implements the P1 contracts: [`asset-ops-004-contract-matrix.md`](./asset-ops-004-contract-matrix.md),
  [`production-asset-metadata-policy.md`](./production-asset-metadata-policy.md),
  [`production-asset-approval-workflow.md`](./production-asset-approval-workflow.md).
- **This PR adds the validator + fixtures + a CI workflow. It does NOT flip branch
  protection and adds NO production assets.** The required check is not enforced until
  DevCTO/Ops apply it (see §Enforcement). Until then the correct status is
  `IMPLEMENTED_PENDING_CI_ENFORCEMENT` — **not** COMPLETE.

## What this is

An **offline, pure-stdlib** validator (`tools/asset_ops/`) that runs all 26 contract
checks (C01–C26) over a production asset *workspace* and emits a deterministic,
machine-readable JSON report. No network, no third-party deps, no image library (PNG
dimensions are read from the IHDR directly). The same code runs locally and in CI.

## Running it

```bash
python -m tools.asset_ops validate --workspace <dir> [--report report.json] [--now ISO] [--quiet]
```

- `--workspace` root uses the layout from `production-asset-metadata-policy.md §2`:
  `assets/metadata/**/*.json`, `assets/source/…`, `assets/generated/manifests/manifest.json`,
  `assets/generated/build-metadata.json`, `assets/releases/rollback-index.json`,
  `assets/approvals/exceptions/*.json`, plus optional `runtime-refs.json` / `bundle-config.json`.
- `--now` fixes the reference time for exception-expiry evaluation (default: current UTC).
  It never appears in the report, so reports stay byte-deterministic.

### Exit codes (contract-matrix §19)

| Code | Meaning | Merge |
|---|---|---|
| 0 | all merge-blocking checks pass (warnings / DEPRECATED excludes allowed) | pass |
| 1 | ≥1 merge-blocking policy/asset violation | block |
| 2 | bad CLI usage / config / input path inaccessible | block |
| 3 | validator internal error / report-generation failure | block |

A JSON report is written on every exit where possible.

### Report

Deterministic (sorted keys, sorted results, LF, trailing newline); contains **no
machine-specific absolute paths, PII, or secrets**. Shape:

```json
{ "schema_version": "1.0.0", "tool_version": "0.1.0",
  "required_check": "asset-production-gate", "build_id": "…",
  "status": "pass|fail|error",
  "summary": { "errors": 0, "warnings": 0, "excluded": 0,
               "passed_checks": 0, "failed_checks": 0 },
  "results": [ { "check_id": "", "code": "", "severity": "", "merge_blocking": true,
    "asset_id": "", "asset_version": "", "artifact_path": "", "message": "",
    "exception_id": null, "details": {} } ] }
```

**Error codes are a stable contract** (§21): codes are deprecated, never repurposed;
adding a code is a tool minor bump; changing a code's meaning is a contract-major bump.
`schema_version` (report) and `tool_version` (validator) are versioned separately.

## Checks (C01–C26)

All 26 rows of the contract matrix are implemented in `tools/asset_ops/checks.py`, each
with a positive fixture (green) and ≥1 targeted negative fixture (red with the exact
code) under `tests/asset_ops/`. Fixtures are **synthetic and materialized at test time**
(a deterministic PNG encoder + the validator's own canonical layer) — nothing is
committed under `assets/metadata/`, per policy §2.

- **Exception-waivable (DevCTO record only):** C15, C16, C17, C18, C26.
- **Never exceptionable:** C01, C10, C12, C13, C14, C22, C25 — including
  `ASSET_ROLLBACK_REVOKED_TARGET` (a rights-revoked asset can never be reactivated by
  rollback; a re-cut or a safe rollback artifact is required).

### Manifest `categoryFallbacks` (C09) + fallback resolution (runtime-aligned)

**Execution contract.** The runtime resolver
`frontend/src/game/pixi/assets/AssetManager.ts` → `resolveTiered` builds a **fixed,
non-recursive candidate sequence from the original request** —
`primary → entry(primary.fallbackAssetId) → category(categoryFallbacks[primary.category])
→ universal` — and never follows a fallback target's own fallback. It is therefore
**cycle-free and bounded to ≤ 3 fallback hops by construction** (duplicate candidates
loaded at most once). The runtime's static `validateManifest` checks entry-fallback
transitive cycles + `categoryFallbacks` key/target existence, and **no** combined
cycle/depth. The validator matches this: it does **not** model a transitive combined
fallback graph, so it never rejects a manifest the runtime resolves safely.

`categoryFallbacks` validation lives entirely in **C09** (metadata-policy §10c):

| Code | Check | Condition |
|---|---|---|
| `ASSET_CATEGORY_FALLBACK_INVALID_KEY` | C09 | field is not an object, or a key is not a runtime `AssetCategory` |
| `ASSET_CATEGORY_FALLBACK_TARGET_MISSING` | C09 | target is not a valid/non-empty assetId, or not present in manifest assets |
| `ASSET_CATEGORY_FALLBACK_TARGET_EXCLUDED` | C09 | target is a known asset but excluded (DEPRECATED/REVOKED/not includable); `details.state` records which |

Target inclusion uses the single `canonical.is_production_includable` predicate, so an
excluded/tampered target is caught. **C10 (`FALLBACK_CYCLE`)** and **C11
(`FALLBACK_DEPTH`)** validate the **metadata entry-fallback graph only** (the
`fallback_asset_id` chain) — C10 mirrors the runtime `validateManifest` transitive
entry-cycle walk; they are unchanged and not repurposed.

**Retired codes.** `ASSET_CATEGORY_FALLBACK_CYCLE` and
`ASSET_CATEGORY_FALLBACK_DEPTH_EXCEEDED` (from an earlier draft) modelled a transitive
combined graph the runtime never traverses; they are **removed before any external
release** and recorded in `core.RETIRED_ERROR_CODES` (never re-used with a new meaning).

**Conformance.** `tests/asset_ops/vectors/fallback_candidate_sequence.json` pins the
runtime candidate sequence; `tools/asset_ops/runtime_contract.py` reproduces it and a
unit test asserts order/dedup/non-recursion/≤3 hops. A future TypeScript runtime test may
read the same vector file.

Coverage evidence: `pytest -q tests/asset_ops` — C09 `categoryFallbacks` negatives
(invalid key, missing/empty target, excluded target, REVOKED target, non-object),
**runtime-valid regressions** (category-target-with-own-fallback and the former depth/cycle
scenarios now PASS), candidate-sequence conformance, determinism, exit-code,
exception-waiver, REVOKED-rollback, and build_id inclusion-set regression tests.

## Shared canonical layer & the inclusion predicate

`tools/asset_ops/canonical.py` holds the **shared canonical primitives** — the inclusion
predicate (`is_production_includable` / `has_production_approval` /
`canonical_included_metadata`), the metadata→manifest field mapping (`metadata_to_entry`),
byte-stable serialization, and the `build_id` envelope. **It is not the production
manifest generator.** The validator (`checks.py`), the build_id included set, and the test
fixture builder all call these primitives, so no component carries its own inclusion rule
or mapping. `checks.py` still owns all detailed C01–C26 error codes and report results;
`canonical.py` only classifies and orders deterministically.

The test fixture builder's `regenerate_derived` is a **test-only workspace assembly
helper** — not the production generator and not the official Metadata→Manifest API. It
calls the canonical primitives so a fixture stays internally consistent; when P3A lands
the official Python generator, `regenerate_derived` will be replaced by a call to it.

**P2 and P3A become aligned "by construction"** only when the P3A generator imports these
same primitives directly. **PR #29 does not implement the production manifest generator.**

## P3A generator — recorded decision

- **Generator runtime:** a **Python build-time tool**, located in **`tools/asset_ops/`**,
  that imports `canonical.py` directly.
- **Official generator:** implemented in **P3A** (not in this PR).
- **Frontend (TypeScript):** consumes the generated manifest JSON **only**.
- **TypeScript must NOT re-implement** any of: the approval/inclusion filter, the
  metadata→manifest mapping, canonical serialization, `build_id`, or exclusion
  classification. Those live once, in `canonical.py`.

## CI

`.github/workflows/asset-production-gate.yml` runs on PRs (and pushes to `main`/`dev`).
The single job lints + type-checks + fixture-tests the validator, then runs the gate
against the repository workspace (`--workspace .`). With no production assets present the
gate exits 0; once production metadata/manifests/releases land under `assets/`, the same
step enforces C01–C26 and blocks on any merge-blocking violation.

## Enforcement (branch protection) — PENDING DevCTO/Ops approval

**The required check-run name is exactly `asset-production-gate`** (the job name).
Branch protection must reference this **check-run name**, not the workflow name.

This is **not applied by this PR.** After the workflow has produced at least one run on
the target branch, an admin applies it (example, requires admin token):

```bash
# Add asset-production-gate to the existing required checks on `main`
gh api -X PATCH repos/<org>/<repo>/branches/main/protection/required_status_checks \
  -f 'checks[][context]=asset-production-gate'
```

Evidence to record when applied (attach to the ASSET-OPS-004 tracking item):
1. `gh api repos/<org>/<repo>/branches/main/protection/required_status_checks` output
   showing `asset-production-gate` present.
2. A screenshot / link of a PR where the `asset-production-gate` check is **Required**.
3. Approver (DevCTO or designated Ops) + timestamp.

If the org cannot host GitHub Actions, an equivalent **enforced** pre-merge gate must be
documented; a purely local script is `CLI_IMPLEMENTED`/`FIXTURE_TESTED`, not
`REQUIRED_CHECK_ENFORCED` (contract-matrix §status model).

## Bypass / exception procedure

- Budget/technical overages (C15/C16/C17/C18/C26) require a **DevCTO exception record**
  under `assets/approvals/exceptions/` (fields per approval-workflow §5); CI validates it
  (present, active, unexpired, approver=DevCTO, asset+version+check matched) before
  treating the check as waived. A waiver without a valid record stays a hard error.
- Rights/approval/integrity/determinism/rollback checks are **never** bypassable.
- Emergency merge with the gate red requires a repo admin to temporarily lift branch
  protection — an audited action, recorded on the tracking item, never the default path.

## Status model

```
POLICY_DEFINED               (P1)
CLI_IMPLEMENTED              ✔ this PR — validator CLI exists
FIXTURE_TESTED               ✔ this PR — all positive + negative fixtures pass
CI_INTEGRATED                ✔ this PR — workflow runs on PRs
REQUIRED_CHECK_ENFORCED      ✘ pending — DevCTO/Ops apply branch protection (§Enforcement)
COMPLETE                     ✘ pending — enforced check + bypass doc + DevCTO sign-off
```

Current: **IMPLEMENTED_PENDING_CI_ENFORCEMENT.** Promote to COMPLETE only after the
required check is wired and DevCTO sign-off is recorded.

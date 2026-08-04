# ASSET-OPS-004 — Validator Contract Matrix (P1)

- Owner: Ops (impl at P2) / Program (policy) · Status: **ASSET-OPS-004:
  POLICY_DEFINED_IMPLEMENTATION_PENDING**
- Policy only. Enumerates every check P2 must implement, each with a rule, error code,
  severity, merge-blocking flag, and required positive/negative fixture. **No workflow
  code, no CI, no assets in this PR.** Companion to
  [`production-asset-metadata-policy.md`](./production-asset-metadata-policy.md) and
  [`production-asset-approval-workflow.md`](./production-asset-approval-workflow.md).

## Contract matrix (§27)

Severity: **E** = hard error (merge-blocking), **W** = warning. "Excl" = exclude-with-report
(non-error). Every check requires a valid fixture (passes) and ≥1 invalid fixture (fails
with the code). Owner: **I**=infra (P2 validator/CI), **F**=frontend (P3 generator hook).

| ID | Check | Input | Rule | Error code | Sev | Blocks | Owner |
|---|---|---|---|---|---|---|---|
| C01 | schema validation | metadata | matches metadata JSON Schema | `SCHEMA_INVALID` | E | yes | I |
| C02 | duplicate assetId+version | metadata set | `(asset_id, asset_version)` unique | `DUP_ASSET_VERSION` | E | yes | I |
| C03 | duplicate frame | atlas metadata | `(atlas_id, atlas_version, frame_name)` unique | `DUP_FRAME` | E | yes | I |
| C04 | source exists | metadata + fs | `source_path` binary exists | `SOURCE_MISSING` | E | yes | I |
| C05 | atlas JSON↔image | atlas | JSON exists; image exists; JSON-referenced image name/path == metadata `atlas_image_path`; every frame within image bounds; no dup frame; metadata `frame` present | `ATLAS_INCONSISTENT`, `ASSET_ATLAS_IMAGE_REFERENCE_MISMATCH` | E | yes | I |
| C06 | frame-name convention | atlas | frame names match convention | `FRAME_NAME_INVALID` | E | yes | I |
| C07 | anchor range | metadata | anchor x/y ∈ [0,1] | `ANCHOR_RANGE` | E | yes | I |
| C08 | footprint range | metadata | footprint w/h ∈ 1..4 integer | `FOOTPRINT_RANGE` | E | yes | I |
| C09 | fallback exists | metadata | `fallback_asset_id` resolves | `FALLBACK_MISSING` | E | yes | I |
| C10 | fallback cycle | metadata graph | no entry/category cycle | `FALLBACK_CYCLE` | E | yes | I |
| C11 | fallback depth | metadata graph | chain ≤ 3 hops | `FALLBACK_DEPTH` | E | yes | I |
| C12 | source-artifact checksum integrity | metadata + artifacts | **image:** `checksum_sha256` matches source (64-hex). **atlas:** `atlas_json_checksum_sha256` matches JSON **and** `atlas_image_checksum_sha256` matches image; both required; report which artifact failed | `ASSET_CHECKSUM_IMAGE_MISMATCH`, `ASSET_CHECKSUM_ATLAS_JSON_MISMATCH`, `ASSET_CHECKSUM_ATLAS_IMAGE_MISMATCH` | E | yes | I |
| C13 | license metadata | metadata | `license_type != unknown` + evidence per license model | `LICENSE_INVALID` | E | yes | I |
| C14 | production approval | metadata | `APPROVED_FOR_PRODUCTION` + complete approval record, version-bound | `APPROVAL_INVALID` | E | yes | I |
| C15 | texture dimension | metadata + image | ≤ 2048 recommended; ≤ 4096 hard-max **or** valid exception | `TEXTURE_DIMENSION` | E | yes | I |
| C16 | atlas dimension | atlas image | ≤ 2048 / ≤ 4096 (POT for atlas) or exception; padding ≥2px, extrusion ≥1px | `ATLAS_DIMENSION` | E | yes | I |
| C17 | compressed bundle size | bundle | ≤ transfer budget (measured basis, FU-009) | `BUNDLE_SIZE` | E | yes | I |
| C18 | estimated GPU memory | metadata | critical ≤ 32 MiB; resident ≤ 64 MiB (incl. mipmap/4096² accounting) | `GPU_MEMORY` | E | yes | I |
| C19 | unused manifest entry | manifest vs runtime refs | no manifest asset unreferenced by runtime kinds | `UNUSED_ENTRY` | W | no | I |
| C20 | unmanifested runtime asset | runtime refs vs manifest | every runtime-needed asset id is in the manifest | `UNMANIFESTED_ASSET` | E | yes | I/F |
| C21 | metadata↔manifest mapping | metadata + generated manifest | mapping (§10 of metadata policy) exact; no governance field leaked | `MAPPING_MISMATCH` | E | yes | F |
| C22 | deterministic generation | metadata | regenerate ⇒ byte-identical to committed manifest | `NONDETERMINISTIC` | E | yes | F |
| C23 | bundle dependency cycle | bundle graph | no cycle; shared asset single-owner | `BUNDLE_CYCLE` | E | yes | I |
| C24 | build-id consistency | manifest + build meta | `build_id` = hash of canonical metadata + gen/schema version | `BUILD_ID_MISMATCH` | E | yes | F |
| C25 | rollback artifact | release | rollback index present + consistent; **every asset in a rollback CANDIDATE manifest checked against current approval state — a candidate containing a REVOKED asset is INELIGIBLE; ≥1 safe (no-REVOKED) rollback artifact must exist**; presence alone is not sufficient | `ROLLBACK_MISSING`, `ASSET_ROLLBACK_REVOKED_TARGET` | E | yes | I |
| C26 | stale-version retention | cache/release policy | superseded versions within retention budget | `STALE_RETENTION` | E (Excl if within grace) | yes | I |

Completion evidence per row: valid fixture green + each invalid fixture red with the exact
code. Fixtures live under `tests/assets/fixtures/` (never `assets/metadata/`).

## ASSET-OPS-004 status model (§28)

```
POLICY_DEFINED                     ← here (P1)
CLI_IMPLEMENTED                    ← P2: validator CLI exists
FIXTURE_TESTED                     ← all positive + negative fixtures pass
CI_INTEGRATED                      ← runs in CI on PRs
REQUIRED_CHECK_ENFORCED            ← wired as a required check that blocks merge
COMPLETE                           ← all of the above + bypass procedure documented + DevCTO sign-off
```

- **ASSET-OPS-004 is COMPLETE only when**: validator CLI implemented; all positive/negative
  fixtures pass; runs in CI; wired as a **required** merge-blocking check; the exception/
  bypass procedure is documented; DevCTO sign-off recorded.
- If there is **no CI workflow** or the required check is not enforced, the correct status is
  **`IMPLEMENTED_PENDING_CI_ENFORCEMENT`** — **not** COMPLETE.
- A GitHub Actions workflow is the one place `.github/workflows` scope opens (P2 only). If
  the org cannot host CI, an equivalent enforced pre-merge gate must be documented; a purely
  local script is `CLI_IMPLEMENTED`/`FIXTURE_TESTED`, not `REQUIRED_CHECK_ENFORCED`.

## Validator interface (P2 implementation contract)

**Required check name (fixed):** `asset-production-gate`. Branch protection must use this
**exact check-run name** (not merely a workflow name). Renaming it changes policy + workflow
+ branch protection **atomically**. Without a wired required check, ASSET-OPS-004 is not
COMPLETE (§status model).

**Exit codes (§19 of corrections):**

| Code | Meaning | Merge |
|---|---|---|
| 0 | all merge-blocking checks pass (warnings-only, or DEPRECATED exclude-with-report + intact reference integrity, are allowed) | pass |
| 1 | ≥1 merge-blocking policy/asset violation | **block** |
| 2 | bad CLI usage / config error / input path inaccessible | **block** |
| 3 | validator internal error / unhandled exception / report-generation failure | **block** |

A JSON report is emitted on every exit where possible.

**Machine-readable report (§20):**

```json
{ "schema_version": "...", "tool_version": "...", "required_check": "asset-production-gate",
  "build_id": "...", "status": "pass|fail|error",
  "summary": { "errors": 0, "warnings": 0, "excluded": 0, "passed_checks": 0, "failed_checks": 0 },
  "results": [ { "check_id": "", "code": "", "severity": "", "merge_blocking": true,
    "asset_id": "", "asset_version": "", "artifact_path": "", "message": "",
    "exception_id": null, "details": {} } ] }
```

Results ordering deterministic; **no machine-specific absolute paths, PII, or secrets**; a
human-readable summary is derived from the same results.

**Error-code compatibility (§21):** error codes are a stable automation/CI-annotation
contract. A code's meaning is never repurposed; codes are deprecated, not deleted; adding a
code is a tool **minor** version; changing a code's meaning is a **major**/contract version.
Report `schema_version` and validator `tool_version` are managed separately.

## Exception verification (§29)

Checks C15/C16/C17/C18/C26 may be waived **only** by a DevCTO exception record
(`production-asset-approval-workflow.md §5`) that CI validates (present, active, unexpired,
version-and-check matched). **C01 / C10 / C12 / C13 / C14 / C22 / C25 are NEVER
exceptionable** — including `ASSET_ROLLBACK_REVOKED_TARGET`: **not even DevCTO may approve
reactivating a rights-revoked asset**; a re-cut or a safe rollback artifact is required.

## Status
Contract defined; **not** implemented. Owners: matrix `Owner` column. Next: P2 implements
C01–C26 as an offline validator with fixtures, then wires a required CI check.

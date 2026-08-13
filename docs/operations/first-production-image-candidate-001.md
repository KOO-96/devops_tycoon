# First Production Image Candidate #001 — APP Server Building

- Candidate: **APP Server Building** · asset_id `building.app-server.primary` · asset_version `1`
- Status: **READY_FOR_DEVCTO_GATE_REVIEW** · First Production Image Asset Gate: **CLOSED**
- This document is the canonical governance record referenced by the asset metadata
  (`assets/metadata/building/app-server.json`) fields `license_reference`,
  `approval.rights_review_reference`, `approval.technical_review_reference`.

## Asset identity

| Field | Value |
|---|---|
| asset_id | `building.app-server.primary` |
| asset_version | `1` |
| category | `building` (runtime AssetCategory) |
| semantic_role | `building-structure` |
| source_type | `image` (single texture; **not** atlas, **not** generated) |
| source_path | `assets/source/building/app-server.png` |
| format | PNG (RGBA8) |
| dimensions | 512 × 512 (≤ 2048 recommended; normal path, **no** 4096² exception) |
| encoded bytes | 6000 |
| alpha | **TRUE_ALPHA** — opaque 37.30% / partial 2.51% / transparent 60.19% (file-level PNG alpha, not appearance) |
| checksum_sha256 | `5507a77ce21c11eb427d03a44a95a4fe32f906e8be43bb6fe0dc7286af894e96` |
| bundle | `critical-core` |
| anchor / footprint | `{x:0.5, y:1.0}` / `{width:1, height:1}` |

## License {#license}

- **license_type: `company_owned`.** The asset is owned by the DevOps Tycoon project.
- **Rights holder:** DevOps Tycoon project. **Original author:** the project's internal
  procedural asset tooling (deterministic PIL render). No third-party content, no external
  reference image reproduced, no external license obligations, no attribution required.
- Not a placeholder (`unknown`/`TBD`/`TEMP` are **not** used).

## Rights review {#rights-review}

- Origin is fully internal (`original_internal`); the building silhouette, rack, LEDs, and
  "APP" plate are procedurally composed — **no external asset, photo, logo, or trademark** is
  incorporated. `reference_usage: none`.
- Redistribution / runtime use / commercial use: permitted (project-owned).
- Conclusion: **rights clear for production use.**

## Technical review {#technical-review}

- Dimensions 512×512 → C15 PASS (≤ 2048 recommended); normal path, no exception.
- GPU estimate `512·512·4 = 1,048,576 B` (1.0 MiB) → C18 critical (≤ 32 MiB) + resident
  (≤ 64 MiB) PASS.
- Encoded transfer 6000 B → C17 critical-core bundle (≤ 8 MiB) PASS.
- TRUE_ALPHA verified from the PNG alpha channel; readable isometric server motif at small scale.
- Deterministic generation: `verify-generated` byte-stable (A==B), no drift, gate PASS.
- Conclusion: **technically compliant with the CONFIRMED Production Image asset budget.**

## Provenance

`source_provenance`: `origin_type: original_internal`, creator = project procedural asset
tooling, `created_at: 2026-08-13`, `human_reviewed: true`, `reference_usage: none`,
`transformation_notes`: deterministic isometric server-building render (PIL, no randomness, no
external reference). Not `generative_output` (no ML model / prompt); a hand-authored procedural
composition.

## Two-tier approval (important)

1. **Asset-metadata production approval** (`approval_state: APPROVED_FOR_PRODUCTION`,
   `approved_by: internal-asset-governance`): rights + technical review above are complete and
   recorded, which lets the generator include the asset and the validator evaluate it. This is
   the asset-governance approval, **not** the release decision.
2. **First Production Image Asset Gate (release):** remains **CLOSED**. Opening it is the
   separate **DevCTO Gate Review** decision (§44 of the candidate task). Implementation does
   **not** open the gate.

## Gate evidence summary

- Generator: included=1, excluded=0, hard_errors=0, build_id `852b76b7…`.
- Validator C01–C26: **26/26 PASS**, 0 errors, 0 warnings.
- verify-generated: nondeterministic=0, schema=0, drift=0, gate=pass.
- C15 PASS · C17 6000 B ≤ 8 MiB (FIRST_PRODUCTION_BUNDLE_TRANSFER_EVALUATION on the actual
  included set = **PASS**) · C18 1 MiB ≤ 32 / 64 MiB · swap peak 2 MiB ≤ 64 MiB.
- Atlas: not used (P3B NOT_IMPLEMENTED). 4096²: not used. BUDGET-RUNTIME-FU-004: not engaged.

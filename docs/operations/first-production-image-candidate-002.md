# Production Image Candidate #002 — Database Building

- Candidate: **Database Building** · asset_id `building.database.primary` · asset_version `1`
- Status: **READY_FOR_DEVCTO_ASSET_REVIEW** · First Production Image Asset Gate: **OPEN_IN_DEV** (unchanged)
- Canonical governance record referenced by `assets/metadata/building/database.json`
  (`license_reference`, `approval.rights_review_reference`, `approval.technical_review_reference`).

## Asset identity

| Field | Value |
|---|---|
| asset_id / version | `building.database.primary` / `1` |
| category / source_type | `building` / `image` (not atlas, not generated) |
| semantic_role | `building-structure` (Database Building) |
| source_path | `assets/source/building/database.png` |
| format / dimensions | PNG RGBA8 / 512×512 (≤ 2048, normal path, no 4096² exception) |
| encoded bytes | 5329 |
| alpha | **TRUE_ALPHA** — opaque 33.21% / partial 3.13% / transparent 63.66% (file-level) |
| checksum_sha256 | `1fa594411c7949d5427d9ca4178631bcff6c9fb44724e05a6d79d859f7f1557d` |
| bundle | `critical-core` |
| anchor / footprint | `{x:0.5, y:1.0}` / `{width:1, height:1}` |

## License {#license}

- **`company_owned`.** Owned by the DevOps Tycoon project; author = the project's internal
  procedural asset tooling (deterministic PIL render). No third-party content, no external
  reference reproduced, no attribution. Not a placeholder.

## Rights review {#rights-review}

- Fully internal (`original_internal`); the stacked-cylinder database silhouette is
  procedurally composed — no external asset/photo/logo/trademark. `reference_usage: none`.
- Rights clear for production use.

## Technical review {#technical-review}

- 512×512 → C15 PASS (≤ 2048). GPU `512·512·4 = 1,048,576 B` (1.0 MiB) → C18 PASS.
- Encoded 5329 B; cumulative critical-core bundle (APP 6000 + DB 5329 = 11,329 B) → C17 PASS (≤ 8 MiB).
- TRUE_ALPHA verified from the PNG channel.
- **Semantic distinction from Candidate #001:** stacked-cylinder / data-vault motif + teal
  palette vs the APP server rack's angular box + slate/LED palette — distinguishable at small
  board scale (not a recolor).

## Provenance

`origin_type: original_internal`, creator = project procedural asset tooling,
`created_at: 2026-08-13`, `human_reviewed: true`, `reference_usage: none`, deterministic
isometric stacked-cylinder render (PIL, no ML model / no prompt / no external reference). Not
`generative_output`.

## Two-tier approval

1. **Asset-metadata production approval** (`APPROVED_FOR_PRODUCTION`, `approved_by:
   internal-asset-governance`) — rights + technical review complete, enabling generator
   inclusion + validation.
2. **DevCTO asset review** — the release decision for this specific asset. The First Production
   Image Asset Gate is already **OPEN_IN_DEV** (opened by candidate #001); #002 does not
   re-open or re-close it. Implementation does not self-approve.

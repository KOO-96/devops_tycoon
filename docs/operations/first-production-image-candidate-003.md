# Production Image Candidate #003 — Redis / Cache Building

- Candidate: **Redis / Cache Building** · asset_id `building.cache.primary` · asset_version `1`
- Status: **READY_FOR_DEVCTO_ASSET_REVIEW** · First Production Image Asset Gate: **OPEN_IN_DEV** (unchanged)
- Canonical governance record referenced by `assets/metadata/building/cache.json`.

## Asset identity

| Field | Value |
|---|---|
| asset_id / version | `building.cache.primary` / `1` |
| category / source_type | `building` / `image` (not atlas, not generated) |
| semantic_role | `building-structure` (Redis / Cache Building) |
| source_path | `assets/source/building/cache.png` |
| format / dimensions | PNG RGBA8 / 512×512 (≤ 2048, normal path, no 4096² exception) |
| encoded bytes | 3795 |
| alpha | **TRUE_ALPHA** — opaque 31.77% / partial 2.63% / transparent 65.60% (file-level) |
| checksum_sha256 | `c8b04ee398af791b3ef5f3edd324d15f9dd226d14f39006d99eb92adc3559d35` |
| bundle | `critical-core` |
| anchor / footprint | `{x:0.5, y:1.0}` / `{width:1, height:1}` |

## License {#license}

- **`company_owned`.** Owned by the DevOps Tycoon project; author = the project's internal
  procedural asset tooling (deterministic PIL render). No third-party content. Not a placeholder.

## Rights review {#rights-review}

- Fully internal (`original_internal`). The cache motif (stacked memory modules + chip pins +
  rapid-access chevron) is procedurally composed — **no Redis brand logo, no external asset,
  photo, or trademark** is incorporated (§4 IP note). `reference_usage: none`.
- Rights clear for production use.

## Technical review {#technical-review}

- 512×512 → C15 PASS (≤ 2048). GPU `512·512·4 = 1,048,576 B` (1.0 MiB) → C18 PASS.
- Encoded 3795 B; cumulative critical-core bundle (APP 6000 + DB 5329 + Cache 3795 = 15,124 B)
  → C17 PASS (≤ 8 MiB).
- TRUE_ALPHA verified from the PNG channel.
- **Semantic distinction:** three distinguishable buildings at board scale —
  APP (slate server rack + LEDs), DB (teal stacked cylinders), **Cache (warm orange/red stacked
  memory modules + chevron)** — different silhouette *and* palette (not a recolor).

## Provenance

`origin_type: original_internal`, creator = project procedural asset tooling,
`created_at: 2026-08-13`, `human_reviewed: true`, `reference_usage: none`, deterministic
isometric stacked memory-module render (PIL, no ML model / no prompt / no external reference /
no Redis brand). Not `generative_output`.

## Two-tier approval

1. **Asset-metadata production approval** (`APPROVED_FOR_PRODUCTION`, `approved_by:
   internal-asset-governance`) — rights + technical review complete, enabling generator
   inclusion + validation.
2. **DevCTO asset review** — the release decision for this asset. The First Production Image
   Asset Gate is already **OPEN_IN_DEV**; #003 does not re-open or close it. Implementation
   does not self-approve.

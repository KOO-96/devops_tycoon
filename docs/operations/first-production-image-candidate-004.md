# Production Image Candidate #004 — Load Balancer Building

- Candidate: **Load Balancer Building** · asset_id `building.load-balancer.primary` · asset_version `1`
- Status: **READY_FOR_DEVCTO_ASSET_REVIEW** · First Production Image Asset Gate: **OPEN_IN_DEV** (unchanged)
- Canonical governance record referenced by `assets/metadata/building/load-balancer.json`.

## Asset identity

| Field | Value |
|---|---|
| asset_id / version | `building.load-balancer.primary` / `1` |
| category / source_type | `building` / `image` (not atlas, not generated) |
| semantic_role | `building-structure` (Load Balancer Building) |
| source_path | `assets/source/building/load-balancer.png` |
| format / dimensions | PNG RGBA8 / 512×512 (≤ 2048, normal path, no 4096² exception) |
| encoded bytes | 4297 |
| alpha | **TRUE_ALPHA** — opaque 23.24% / partial 3.13% / transparent 73.63% (file-level) |
| checksum_sha256 | `02f2545655c6fbe2bb3c4f6399bd57b07d45a5c00fd99d20f0a19d71db6aa9ff` |
| bundle | `critical-core` |
| anchor / footprint | `{x:0.5, y:1.0}` / `{width:1, height:1}` |

## License {#license}

- **`company_owned`.** Owned by the DevOps Tycoon project; author = the project's internal
  procedural asset tooling (deterministic PIL render). No third-party content. Not a placeholder.

## Rights review {#rights-review}

- Fully internal (`original_internal`). The routing-hub motif (input funnel → central node →
  branching output arrows + network ports) is procedurally composed — **no NGINX / HAProxy /
  AWS ELB or any vendor logo/trademark** is incorporated (§4). `reference_usage: none`.
- Rights clear for production use.

## Technical review {#technical-review}

- 512×512 → C15 PASS (≤ 2048). GPU `512·512·4 = 1,048,576 B` (1.0 MiB) → C18 PASS.
- Encoded 4297 B; cumulative critical-core bundle
  (APP 6000 + DB 5329 + Cache 3795 + LB 4297 = 19,421 B) → C17 PASS (≤ 8 MiB).
- TRUE_ALPHA verified from the PNG channel.
- **Four-way semantic distinction:** APP (slate server rack + LEDs), DB (teal stacked
  cylinders), Cache (warm orange stacked memory modules), **LB (wide blue routing hub with
  one→many distribution arrows)** — distinct silhouette *and* palette (not a recolor).

## Provenance

`origin_type: original_internal`, creator = project procedural asset tooling,
`created_at: 2026-08-14`, `human_reviewed: true`, `reference_usage: none`, deterministic
isometric routing-hub render (PIL, no ML model / no prompt / no external reference / no vendor
logo). Not `generative_output`.

## Two-tier approval

1. **Asset-metadata production approval** (`APPROVED_FOR_PRODUCTION`, `approved_by:
   internal-asset-governance`) — rights + technical review complete, enabling generator
   inclusion + validation.
2. **DevCTO asset review** — the release decision for this asset. The First Production Image
   Asset Gate is already **OPEN_IN_DEV**; #004 does not re-open or close it. Implementation
   does not self-approve.

# First Production Effect Candidate #005 — Network Flow Effect

- Candidate: **Network Flow Effect** · asset_id `effect.network-flow.primary` · asset_version `1`
- Status: **READY_FOR_DEVCTO_EFFECT_ASSET_REVIEW** · First Production Image Asset Gate: **OPEN_IN_DEV**
- **Approval scope (important):** this approves the **image resource** for production use through
  the Production Image Pipeline. It is **NOT** an EVENT_DERIVED effect approval — POLICY-C-FU-002
  is `NOT_IMPLEMENTED`, so this asset is **not** wired to any simulation event/incident. State:
  `APPROVED_BUT_EVENT_UNWIRED`.
- Canonical governance record referenced by `assets/metadata/effect/network-flow.json`.

## Asset identity

| Field | Value |
|---|---|
| asset_id / version | `effect.network-flow.primary` / `1` |
| category / source_type | `effect` (canonical AssetCategory) / `image` (not atlas, not generated) |
| semantic_role | `effect-visual` (Network Flow Effect) |
| source_path | `assets/source/effect/network-flow.png` |
| format / dimensions | PNG RGBA8 / 1024×256 (≤ 2048, normal path, no 4096² exception) |
| encoded bytes | 2089 |
| alpha | **TRUE_ALPHA** — opaque 0.26% / **partial 7.52%** / transparent 92.22% (file-level) |
| visible-alpha bbox | 933×61 (21.7% of canvas); thin horizontal flow beam |
| checksum_sha256 | `d4c2dd4e7873479cc6ceff00394c28c7149561d468bb0f56d65b257b122b56e9` |
| bundle | `critical-core` |

Effect assets carry no `anchor`/`footprint` (not a building). Not reused from the FU-009
NON_PRODUCTION_REPRESENTATIVE_EVIDENCE — a separate project-owned production source.

## License {#license}

- **`company_owned`.** Owned by the DevOps Tycoon project; author = project procedural asset
  tooling (deterministic PIL render). No third-party content. Not a placeholder.

## Rights review {#rights-review}

- Fully internal (`original_internal`). The data-flow beam (glow line + packet dots + arrow) is
  procedurally composed — **no AWS / Cloudflare / Cisco / NGINX / HAProxy or any vendor
  logo/trademark** (§13). `reference_usage: none`.
- Rights clear for production use.

## Technical review {#technical-review}

- 1024×256 → C15 PASS (≤ 2048). GPU `1024·256·4 = 1,048,576 B` (1.0 MiB) → C18 PASS.
- Encoded 2089 B; cumulative critical-core bundle
  (APP 6000 + DB 5329 + Cache 3795 + LB 4297 + Effect 2089 = 21,510 B) → C17 PASS (≤ 8 MiB).
- **TRUE_ALPHA** with real partial-alpha glow (7.52%) — proper transparent overlay, not a solid
  rectangle / baked checkerboard.
- **Optimization follow-up (non-blocking):** the 256px-tall canvas is ~76% vertical transparent
  padding around a ~61px flow band; a future crop (e.g. 1024×96) would reduce GPU texture cost.
  No new budget threshold is introduced; 1.0 MiB is well within budget.

## Provenance

`origin_type: original_internal`, creator = project procedural tooling, `created_at: 2026-08-14`,
`human_reviewed: true`, `reference_usage: none`, deterministic directional data-flow render (PIL,
no ML model / no prompt / no external reference / no vendor logo). Not `generative_output`.

## Approval boundary (two-tier + event guard)

1. **Asset-metadata production approval** (`APPROVED_FOR_PRODUCTION`) — the image resource is
   approved; enables generator inclusion + validation + isolated runtime preview.
2. **DevCTO effect-asset review** — release decision for the image resource.
3. **EVENT_DERIVED runtime is OUT OF SCOPE.** No `event.type → effect`, no incident spawn, no
   scheduler, no effect lifetime policy. POLICY-C-FU-002 stays `NOT_IMPLEMENTED`. The asset is
   validated only via an **isolated effect preview** harness, never wired to game events.

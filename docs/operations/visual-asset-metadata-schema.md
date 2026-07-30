# Visual Asset Metadata Schema (ASSET-OPS-001)

- Owner: Infra/Platform · Status: **ASSET-OPS-001: REVIEW_PENDING**
- Base: dev `65adf13`. Documentation/schema design only — no product code, no CI
  workflow, no final assets.

Separates the **Runtime Manifest** (what the app loads — see
`visual-asset-manifest-policy.md`) from **Production Metadata** (provenance, rights,
approval, integrity). This document defines the Production Metadata record.

## Why separate

The Runtime Manifest ships in the bundle and is read every load; Production Metadata
is governance data used at build/merge/audit time. They are linked by
`asset_id + asset_version` but are stored separately so runtime payloads stay small
and rights data isn't shipped to clients.

## Required metadata fields

| Field | Type | Notes |
|---|---|---|
| `asset_id` | string | stable id, unique with version |
| `asset_version` | string | semver-ish; bump on any content change |
| `category` | enum | building / tile / effect / ui / character / fallback / background |
| `display_name` | string | human label |
| `repository_path` | string | committed binary path (or "generated") |
| `source_type` | enum | see below |
| `author_or_tool` | string | person or tool that produced it |
| `created_at` | ISO-8601 | |
| `modified_at` | ISO-8601 | |
| `modified_by` | string | |
| `license_type` | enum | e.g. internal / CC-BY / commercial / `unknown` |
| `license_reference` | string | URL / file / contract id |
| `derivative` | bool | derived from another asset? |
| `derivative_of` | string\|null | source asset id/reference when derivative |
| `production_approved` | bool | governance gate |
| `approved_by` | string\|null | |
| `approved_at` | ISO-8601\|null | |
| `checksum_sha256` | string | integrity; links binary ↔ metadata |
| `logical_width` | int | logical px (64×32 source module, UI-D-002) |
| `logical_height` | int | |
| `pixel_width` | int | actual raster px |
| `pixel_height` | int | |
| `anchor` | {x,y} | 0..1 |
| `footprint` | {width,height} | 1..4 |
| `atlas_id` | string\|null | when packed |
| `frame_name` | string\|null | when packed |
| `tags` | string[] | |

### `source_type` values
`original_internal`, `generated`, `licensed_third_party`, `derived_internal`,
`generated_placeholder`.

### Generative-tool assets — additional fields (recommended)
`generation_tool`, `generation_tool_version`, `model_identifier`,
`prompt_reference` **or** `prompt_hash`, `post_processing`, `human_reviewed`.
Storing the full prompt text is **not** mandatory (a reference/hash suffices).

## Rights policy (Confirmed intent; gates)

- `license_type == unknown` → **must not** be merged to production.
- `production_approved == false` → **must not** appear in a Runtime Production Manifest.
- External reference images **must not** be included as Runtime assets, and the
  original reference **must not** be reproduced (logo/buildings/characters/icons).
- Generative-tool output is **not** auto-approved for production (`human_reviewed`
  + `production_approved` required).
- Derivative assets must record `derivative_of`.
- Fonts / icons / sprites of unclear provenance are prohibited.
- Every final binary must link to metadata via `checksum_sha256`.

The current development **generated fallback** is allowed under
`category = fallback`, `source_type = generated_placeholder` (not a production art
asset).

## Storage

Production Metadata lives alongside the manifest tooling (e.g.
`assets/metadata/<asset_id>@<version>.json`) — **path/format to be finalized with
the manifest tooling (ASSET-OPS-004)**. This document fixes the field set and gates,
not the storage layout.

## Status
**ASSET-OPS-001: REVIEW_PENDING** — field set + rights gates defined; not promoted
to Confirmed. Reviewed with ASSET-OPS-002 + Manifest Baseline + BACK-FU-009 context.

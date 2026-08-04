# Production Asset Metadata — Canonical Policy (Asset Production Enablement P1)

- Owner: Program · Status: **P1: POLICY_DEFINED_PENDING_DEVCTO_REVIEW**
- Scope: policy/contract only. **No** validator, generator, CI, or asset in this PR.
- Relationship: extends `visual-asset-metadata-schema.md` (ASSET-OPS-001 field set) and
  `visual-asset-manifest-policy.md` (runtime manifest). The **runtime consumption**
  (AssetManager, fallback, checksum verify) is already `IMPLEMENTED_IN_DEV` — this
  document governs the **build-time input side** feeding it.

Pipeline this policy governs:
`Production Metadata → validation → approval → deterministic Runtime Manifest → CI gate → release`.

## 1. Canonical source (POLICY-C-FU-005 basis)

- **Production Metadata is the single governance source of record.** Human-authored
  and human-reviewed. Carries license, approval, source provenance, budget-relevant
  dimensions. **Not consumed by the runtime directly.**
- **Runtime Manifest is GENERATED, deterministically, from approved metadata.** Never
  hand-edited. Contains only fields the runtime needs; excludes all governance/PII.
- **Prohibited:** dual manual entry of the same fact in metadata and manifest; editing
  a generated manifest by hand; back-syncing a hand-edited manifest into metadata;
  including non-approved metadata in a production manifest.
- Conflict rule: if metadata and a committed manifest ever disagree, **metadata wins**
  and the manifest is regenerated; a hand-edit is a CI failure (deterministic-generation
  check, `asset-ops-004-contract-matrix.md`).

## 2. Repository layout (proposed; confirm at P2)

```
assets/
  metadata/              # Production Metadata (governance source of record)
    buildings/  status/  decorations/  effects/  ui/
  source/                # committed source binaries (image/atlas)
  generated/
    manifests/           # generated Runtime Manifests (see §Generator output for commit policy)
    reports/             # mapping / exclusion / validation reports (CI artifacts)
  releases/              # release artifacts + rollback index
  approvals/             # approval + exception records (governance, never in runtime manifest)
tests/assets/fixtures/   # validator positive/negative FIXTURES — NEVER mixed with assets/metadata
```

- **Test fixtures live under `tests/assets/fixtures/`, never under `assets/metadata/`.**
  A validator must treat anything under `assets/metadata/` as real governance input.
- `generated/` is machine-owned; a human editing it is a policy violation.
- The `generated-placeholder` development assets currently shipped in code (dev
  fallbacks) are **not** production metadata and do not live here.

## 3. Version fields & bump rules (§6)

| Field | Meaning | Increments when |
|---|---|---|
| `schema_version` | structure/shape of the metadata record | the metadata schema changes (breaking = major) |
| `metadata_version` | revision of this governance record | any metadata edit (incl. description-only), audit trail |
| `asset_version` | runtime cache / release identity of the asset | the **runtime result** changes (binary, or anchor/footprint/frame that alters render) |
| `manifest_version` | version of a generated runtime manifest bundle | a manifest is regenerated with a changed asset set/versions |
| `bundle_version` | deployed bundle version | a bundle's contents change |
| `build_id` | identifier of one deterministic generation output | recomputed each generation (see §9) — deterministic from inputs |

Prohibited: `checksum` used as `asset_version`; `metadata_version` conflated with
`asset_version`; `manifest_version` conflated with `build_id`.

## 4. Asset identity (§7)

- **Canonical identity = `asset_id + asset_version`.** The runtime manifest maps to
  `assetId + assetVersion`; the cache key is `assetId@assetVersion` (already in dev).
- `asset_id` is globally stable: never reused across a rename; **never reused for a
  different-meaning asset**; a rename keeps the id and updates only display fields.
- `asset_version` **increments** when the binary changes, or when anchor/footprint/frame
  changes alter the runtime result. It **may stay** when only description/tags/provenance
  notes change (no runtime-result change).
- **Naming convention:** `<category>.<subject>[.<variant>].<qualifier>`, lower-kebab
  segments. Examples: `building.load-balancer.primary`, `building.app-server.primary`,
  `status.incident.badge`, `fallback.building.generated`. **`.primary`/production ids are
  NOT auto-derived from the current `*.dev` development placeholder ids** — a dev
  placeholder never auto-promotes to an approved production id.

## 5. Asset categories (§8)

Aligned to the runtime `AssetCategory` union (`building | tile | effect | ui | character
| fallback`), plus governance categories the runtime maps down as needed.

| Category | Allowed source types | Runtime use | Required metadata (beyond base) | Default fallback | Budget applied | Prod approval required |
|---|---|---|---|---|---|---|
| `building` | image, atlas | functional node sprite | anchor, footprint | category → universal | texture/atlas/GPU | **yes** |
| `status` | image, atlas | incident/status overlay | anchor | status → universal | texture/atlas | **yes** |
| `decoration` | image, atlas | non-functional decor | anchor | decoration → universal | texture/atlas + resident | **yes** |
| `effect` | image, atlas | (future) effect frames | — | none | animation caps | **yes**, and **gated by POLICY-C-FU-002** |
| `ui` | image, atlas | HUD/panel art | anchor | ui → universal | texture | **yes** |
| `fallback` | generated | terminal/universal placeholder | — | terminal | resident | n/a (code-generated) |

- **`effect` existing here does NOT make event-driven effects production-ready.**
  EVENT_DERIVED remains `NOT_IMPLEMENTED` (POLICY-C-FU-002); no `effect` asset may ship
  as an active event effect until FU-002 is authored and approved.
- `characters-phase2` bundle assets are out of the first-gate scope.

## 6. Source types (§9)

| `source_type` | Meaning | In first production gate? |
|---|---|---|
| `image` | single texture (one binary) | **yes** |
| `atlas` | atlas image + atlas JSON | **yes** |
| `generated` | code-generated runtime fallback — **not a production binary** | n/a (never a production-approved art asset) |
| `font` | font file | **out of scope** for this gate (separate later approval) |

The schema must **reject unsupported source types** rather than silently accept
unknown fields, so the validator never trusts meaningless input.

## 7. License model (§12)

`license_type` allowed values and evidence requirements:

| `license_type` | Evidence required | Production allowed |
|---|---|---|
| `company_owned` | original author + rights-holder identity recorded | yes |
| `commissioned` | rights-assignment reference (contract id) | yes |
| `commercial_license` | license reference + proof-of-purchase/scope reference | yes |
| `open_license` | license name + version + attribution obligation recorded | yes |
| `generative_output` | tool/model + prompt_hash + human_reviewed + rights disposition | yes, **not auto-approved** |
| `unknown` | — | **NO — hard error** |

Prohibited: a bare URL as complete rights proof; reproduction of a reference image just
because it exists; production approval implied by mere use of a generative model.

## 8. Source provenance model (§13)

```
source_provenance:
  origin_type: original_internal | commissioned | licensed_third_party | generative_output | derived_internal
  creator:                 # person/org identity
  created_at:              # UTC ISO-8601
  source_reference:        # contract/purchase/repo reference (NOT the only rights proof)
  generation_model:        # generative only
  generation_tool:         # generative only
  prompt_hash:             # audit reference; full prompt text NOT required
  human_reviewed: true|false
  reference_usage: none | mood | composition | style-study   # bounded; never reproduction
  transformation_notes:
  derivative_of:           # when derived
```

- Full prompt text is **not** a required stored artifact; `prompt_hash` is the audit
  reference. External reference **reproduction is prohibited**; `reference_usage` may only
  be a bounded study category. **Human review is mandatory.** Generative assets still pass
  license + production approval separately.

## 9. Deterministic generation (POLICY-C-FU-005 completion contract)

"Byte-stable" is defined so P3's generator has an exact contract:

- Input metadata canonicalized: object keys sorted lexicographically; arrays sorted by a
  declared stable key (assets by `asset_id` then `asset_version`; frames by `frame_name`).
- Output: UTF-8, LF newlines, single trailing newline, no BOM; 2-space indent; numbers in
  shortest round-trip form; booleans/null literal.
- **No timestamps, hostnames, absolute/system paths, usernames, or env-varying values** in
  the runtime manifest. Any build time/host goes into a **separate** build-metadata file,
  not the manifest.
- **Guarantee:** identical approved-metadata input + identical generator version ⇒
  **byte-for-byte identical** runtime manifest.
- `build_id = sha256(canonical_approved_metadata + generator_version + schema_version)` —
  deterministic. Any time-based/random build id is a **separate** build-metadata field,
  never mixed into the deterministic manifest.

## 10. Metadata → Runtime Manifest field mapping (§16 — P3 implementation contract)

| Metadata field | Runtime manifest field |
|---|---|
| `asset_id` | `assetId` |
| `asset_version` | `assetVersion` |
| `category` | `category` |
| `source_type` | `sourceType` |
| `source_path` | `source` |
| atlas `frame_name` | `frame` |
| `checksum_sha256` | `checksum` |
| `anchor` | `anchor` |
| `footprint` | `footprint` |
| `fallback_asset_id` | `fallbackAssetId` |
| `bundle` | `bundleId` |
| (per-category) `category` fallback set | manifest `categoryFallbacks` |

**Excluded from the runtime manifest (governance/PII only):** `approved_by`,
`approved_at`, `approval_state`, `metadata_version`, rights-evidence internal paths,
`review_notes`/review references, prompt text, exception memos, `source_provenance`.

## 11. Generator output policy (§18) & atomicity (§19)

Generator outputs and their disposition:

| Output | Disposition |
|---|---|
| Runtime Manifest | **committed** (atomic with binary + metadata) |
| Mapping report | CI artifact |
| Exclusion report | CI artifact (also surfaced in PR) |
| Validation summary | CI artifact |
| Build metadata (build_id, time/host) | release artifact (NOT the manifest) |
| Rollback index | release artifact, committed under `assets/releases/` |

**Atomicity — the first production asset PR must:** include Metadata + Binary + regenerated
Manifest + checksum + build_id + validation report **together**. CI blocks: binary changed
but manifest not regenerated; metadata changed but binary missing; manifest hand-edited
(regeneration diff ≠ ∅); checksum mismatch; build_id inconsistent. The committed manifest
policy satisfies the First-Production-Asset gate's "binary + manifest atomically" rule.

## Status
P1 policy defined; **not** implemented. Companion docs:
[`production-asset-approval-workflow.md`](./production-asset-approval-workflow.md) ·
[`asset-ops-004-contract-matrix.md`](./asset-ops-004-contract-matrix.md) ·
[`production-asset-budget-confirmation.md`](./production-asset-budget-confirmation.md) ·
[`first-production-asset-gate.md`](./first-production-asset-gate.md).

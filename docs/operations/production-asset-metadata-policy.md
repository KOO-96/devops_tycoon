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
  segments (the `<category>` prefix is a runtime `AssetCategory`). Examples:
  `building.load-balancer.primary`, `building.app-server.primary`, `ui.incident.badge`,
  `fallback.building.generated`. **`.primary`/production ids are NOT auto-derived from the
  current `*.dev` development placeholder ids** — a dev placeholder never auto-promotes to
  an approved production id.
- **Atlas `asset_version` bump (§13 of corrections)** — increment on: atlas image binary
  change · atlas JSON change · frame coordinate change · frame-name change · atlas image
  reference change · anchor/footprint change · any packing change that alters the runtime
  result. It **may stay** when only description/review notes change (identical runtime
  result). Image assets follow the same rule on their single binary.

## 5. Asset categories (§8) — EXACTLY the runtime `AssetCategory` union

Metadata `category` **is** the runtime `AssetCategory` enum; it maps **1:1** to the
manifest `category`. The generator never infers or converts a category. The schema
**must not** allow any value outside this union. A new category may be added **only** by
versioning the runtime type + schema + generator together.

Allowed `category` values (identical to `frontend/src/game/pixi/assets/assetTypes.ts`):

| `category` | Runtime use | Allowed source types | Required metadata (beyond base) | Default fallback | Budget applied | Prod approval |
|---|---|---|---|---|---|---|
| `building` | building/infra node visual | image, atlas | anchor, footprint | category → universal | texture/atlas/GPU | **yes** |
| `tile` | floor / terrain / decorative tile | image, atlas | anchor | tile → universal | texture/atlas | **yes** |
| `effect` | effect visual asset | image, atlas | — | (none) | animation caps | **yes** — but **may NOT be used in an EVENT_DERIVED effect until POLICY-C-FU-002 is complete**; the category existing is **not** a PR D / EVENT_DERIVED approval |
| `ui` | status indicator / icon / HUD | image, atlas | anchor | ui → universal | texture | **yes** |
| `character` | character / operator / avatar visual | image, atlas | anchor | character → universal | texture/atlas + resident | **yes** |
| `fallback` | runtime fallback visual | image, atlas (or the existing code-generated fallback) | — | terminal | resident | **yes if a production binary; the code-generated fallback is NOT production art** |

- `characters-phase2` bundle assets are out of the first-gate scope.

## 5a. Semantic role — governance classification (NOT a runtime category)

The former governance notions `status` and `decoration` are **not** runtime categories.
They are recorded as a separate governance field and **never** substitute for `category`:

```
semantic_role: status-indicator | decorative-prop | terrain | building-structure |
               interface-element | character-visual | fallback-visual | effect-visual
# and/or usage_tags: string[]
```

- `semantic_role` describes intent; the **human author still sets `category`** to the
  correct runtime value (e.g. a status-indicator asset → `category: ui`; a decorative
  tile → `category: tile` or `building`). **The generator does NOT infer
  status→ui or decoration→tile** — `category` is authored, `semantic_role` is advisory.
- `semantic_role` / `usage_tags` are **excluded from the runtime manifest** (governance
  only). `category` must always be one of the runtime-union values in §5.

## 6a. `generated` source type relationship (§8 of corrections)

`generated` remains a runtime `AssetSourceType` but is **NOT** a first-gate production
binary source:

- `generated` = the existing code-generated development / universal fallback textures,
  registered via the **runtime-owned** path (already in dev), not via Production Metadata.
- Production Metadata **does not** register a `generated` binary, and the Production
  Metadata generator **does not** create new `generated` production assets.
- P3 must not damage the existing generated-fallback contract; production art enters only
  as `image` / `atlas`.

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

### 9a. build_id — canonical envelope (§16 of corrections)

`build_id = sha256(canonical_build_id_envelope)`, where the envelope is a canonical
(sorted, deterministic) serialization of:

```
canonical_build_id_envelope:
  schema_version
  generator_version
  generator_config_version
  included_assets:            # ONLY APPROVED_FOR_PRODUCTION assets that enter the manifest
    - asset_id, asset_version                      # sorted by (asset_id, asset_version)
      runtime_affecting_canonical_metadata          # the fields that reach the manifest
      # source-artifact checksums:
      # image  → checksum_sha256
      # atlas  → atlas_json_checksum_sha256, atlas_image_checksum_sha256
```

**Excluded from the envelope** (so they never change `build_id`): DRAFT / *_REVIEW_REQUIRED
/ *_REJECTED / DEPRECATED / REVOKED / any manifest-excluded asset; `approved_by`,
`approved_at`, `review_notes`, host paths, timestamps, machine-specific values.

Consequences: a DRAFT description change does **not** change `build_id`; a changed included
binary (⇒ changed checksum) **does**; a changed included set **does**; a changed
generator/schema/generator-config version **does**. P2 and P3 compute the same `build_id`
because the envelope, the included set (inclusion rule), and the canonical serialization
(§9) are all fixed.

### 9b. build_id location (§17)

`build_id` is **NOT** a runtime manifest **entry** field. It is recorded in a **separate
build-metadata** file; a manifest file-level metadata block and the release artifact may
reference the same `build_id`. Per-asset cache identity stays `assetId + assetVersion`;
`build_id` is never used as `assetVersion` or `manifestVersion`.

## 10. Metadata → Runtime Manifest field mapping (§16 — P3 implementation contract)

Common fields:

| Metadata field | Runtime manifest field |
|---|---|
| `asset_id` | `assetId` |
| `asset_version` | `assetVersion` |
| `category` (runtime union) | `category` |
| `source_type` | `sourceType` |
| `anchor` | `anchor` |
| `footprint` | `footprint` |
| `fallback_asset_id` | `fallbackAssetId` |
| `bundle` | `bundleId` |

**Source & checksum differ by source type** — the runtime `checksum` is **always** the
checksum of the artifact the runtime fetches via `source` (verified against the
`assetManifest` `source`/`frame` contract in dev):

### 10a. `image`

| Metadata | Runtime manifest |
|---|---|
| `source_path` | `source` |
| `checksum_sha256` | `checksum` |

### 10b. `atlas` (two source artifacts — §10–12 of corrections)

```
source:
  type: atlas
  atlas_json_path:            # the descriptor the runtime loads via `source`
  atlas_image_path:
  atlas_json_checksum_sha256:
  atlas_image_checksum_sha256:
  frame:
```

| Metadata | Runtime manifest | Note |
|---|---|---|
| `atlas_json_path` | `source` | runtime fetches the **descriptor JSON** via `source` |
| `frame` | `frame` | |
| `atlas_json_checksum_sha256` | `checksum` | runtime `checksum` = the JSON (the artifact `source` points at) |
| `atlas_image_checksum_sha256` | *(not in manifest)* | verified in governance/CI only (C12) |

Rationale: the runtime entry has a **single** `checksum`, so it binds to the artifact the
runtime directly fetches (the descriptor JSON). The atlas image's integrity is enforced by
CI (C12) and folded into `build_id` (§9a) — the two checksums are **never** synthesized into
one. **P2 and P3 use the same rule: runtime `checksum` = checksum of the file `source`
points to.** (Dev has no real atlas loader yet; this is the forward contract P3 implements.
If a future loader fetches the image directly, `source`→image and `checksum`→image, keeping
the invariant "`checksum` = the file `source` points to".)

### 10c. Category fallbacks (§9 of corrections)

The generator emits manifest `categoryFallbacks: Partial<Record<AssetCategory, string>>`
from a canonical per-category configuration: keys are runtime `AssetCategory` values only;
targets are real `assetId`s that must exist; resolved **after** entry `fallbackAssetId` and
**before** the universal fallback; no cycles; ≤ 3 hops; the generator does **not** infer
targets; deterministic from the same input.

**Excluded from the runtime manifest (governance/PII only):** `approved_by`, `approved_at`,
`approval_state`, `metadata_version`, `semantic_role`, `usage_tags`, `source_provenance`,
rights-evidence internal paths, `review_notes`/review references, prompt text, exception
memos, atlas image checksum.

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

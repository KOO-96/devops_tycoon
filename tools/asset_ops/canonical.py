"""Canonical primitives: inclusion predicate, metadata→manifest mapping, byte-stable
form, build_id.

Provides the shared canonical primitives for validation (checks.py), fixture
generation (the test builder), and the future P3A Python build-time generator. It does
NOT implement the production manifest generator itself — it supplies the deterministic
mapping/serialization/inclusion pieces those callers build on. P2 and P3A become aligned
"by construction" only once the P3A generator imports these primitives directly.
Implements `production-asset-metadata-policy.md §9, §9a, §10, §14`.
"""

from __future__ import annotations

import json
from typing import Any

from .core import EXCLUDED_TERMINAL_STATES, INCLUDABLE_STATE, normalize_checksum

# Governance/PII fields that must NEVER appear in a runtime manifest entry (§10c).
GOVERNANCE_EXCLUDED_MANIFEST_FIELDS: frozenset[str] = frozenset(
    {
        "approved_by",
        "approved_at",
        "approval",
        "approval_state",
        "production_approved",
        "metadata_version",
        "schema_version",
        "semantic_role",
        "usage_tags",
        "source_provenance",
        "review_notes",
        "license_type",
        "license_reference",
        "rights_review_reference",
        "technical_review_reference",
        "atlas_image_checksum_sha256",
        "atlas_image_path",
    }
)


# ---------------------------------------------------------------------------
# Inclusion predicate — THE single canonical rule that decides whether a
# metadata record enters the runtime manifest / build_id set. Reused by the
# validator (checks.py), the fixture builder, the build_id set, and the future
# P3A Python generator. These are deterministic classification primitives ONLY;
# checks.py owns the detailed C01-C26 error codes and report results.
# ---------------------------------------------------------------------------


def has_production_approval(metadata: dict[str, Any]) -> bool:
    """True iff a complete, version-bound production approval record is present.

    (production-asset-approval-workflow.md §11 — approval is bound to
    `reviewed_asset_version`.) Classification primitive only; C14 owns the
    detailed APPROVAL_INVALID reporting.
    """
    if metadata.get("approval_state") != INCLUDABLE_STATE:
        return False
    if metadata.get("production_approved") is not True:
        return False
    approval = metadata.get("approval")
    if not isinstance(approval, dict):
        return False
    return approval.get("reviewed_asset_version") == metadata.get("asset_version")


def is_production_includable(metadata: dict[str, Any]) -> bool:
    """The one inclusion predicate (production-asset-approval-workflow.md §14).

    Deterministic boolean; every failing sub-condition is separately reported with
    its own C01-C26 code by checks.py. Kept minimal per the P2 corrections:
    APPROVED_FOR_PRODUCTION + production_approved true + boolean/state consistency +
    version-bound approval + license != unknown + not DEPRECATED/REVOKED.
    """
    state = metadata.get("approval_state")
    approved = metadata.get("production_approved")
    if (state == INCLUDABLE_STATE) != (approved is True):
        return False  # boolean/state mismatch
    if state in EXCLUDED_TERMINAL_STATES:
        return False  # DEPRECATED / REVOKED never enter a new manifest
    if not has_production_approval(metadata):
        return False  # missing or non-version-bound approval record
    license_type = metadata.get("license_type")
    return isinstance(license_type, str) and license_type != "unknown"


def canonical_included_metadata(metadata_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic manifest-included set: filter by inclusion, sort by identity."""
    included = [m for m in metadata_items if is_production_includable(m)]
    return sorted(
        included,
        key=lambda m: (str(m.get("asset_id")), str(m.get("asset_version"))),
    )


def _atlas_source(data: dict[str, Any]) -> dict[str, Any]:
    src = data.get("source")
    return src if isinstance(src, dict) else {}


def metadata_to_entry(data: dict[str, Any]) -> dict[str, Any]:
    """Produce the runtime manifest entry for a metadata record (§10 mapping).

    Assumes the record already passed schema/type checks; missing values map to None
    so a mapping mismatch (C21) surfaces rather than raising.
    """
    source_type = data.get("source_type")
    entry: dict[str, Any] = {
        "assetId": data.get("asset_id"),
        "assetVersion": data.get("asset_version"),
        "category": data.get("category"),
        "sourceType": source_type,
    }
    if source_type == "atlas":
        src = _atlas_source(data)
        entry["source"] = src.get("atlas_json_path")
        entry["frame"] = src.get("frame")
        checksum = src.get("atlas_json_checksum_sha256")
    else:
        entry["source"] = data.get("source_path")
        checksum = data.get("checksum_sha256")
    entry["checksum"] = normalize_checksum(checksum) if isinstance(checksum, str) else checksum

    if isinstance(data.get("anchor"), dict):
        entry["anchor"] = data["anchor"]
    if isinstance(data.get("footprint"), dict):
        entry["footprint"] = data["footprint"]
    if data.get("fallback_asset_id") is not None:
        entry["fallbackAssetId"] = data.get("fallback_asset_id")
    entry["bundleId"] = data.get("bundle")
    return entry


def canonical_bytes(obj: Any) -> bytes:
    """Byte-stable canonical JSON (§9): sorted keys, 2-space indent, LF, trailing LF."""
    text = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Canonicalize a runtime manifest: assets sorted by (assetId, assetVersion)."""
    out = dict(manifest)
    assets = out.get("assets")
    if isinstance(assets, list):
        out["assets"] = sorted(
            assets,
            key=lambda e: (
                str(e.get("assetId")) if isinstance(e, dict) else "",
                str(e.get("assetVersion")) if isinstance(e, dict) else "",
            ),
        )
    return canonical_bytes(out)


def _envelope_asset(data: dict[str, Any]) -> dict[str, Any]:
    source_type = data.get("source_type")
    entry = metadata_to_entry(data)
    if source_type == "atlas":
        src = _atlas_source(data)
        source_checksums = {
            "atlas_json": _norm_opt(src.get("atlas_json_checksum_sha256")),
            "atlas_image": _norm_opt(src.get("atlas_image_checksum_sha256")),
        }
    else:
        source_checksums = {"image": _norm_opt(data.get("checksum_sha256"))}
    return {
        "asset_id": data.get("asset_id"),
        "asset_version": data.get("asset_version"),
        "category": data.get("category"),
        "source_type": source_type,
        "anchor": data.get("anchor"),
        "footprint": data.get("footprint"),
        "fallback_asset_id": data.get("fallback_asset_id"),
        "bundle": data.get("bundle"),
        "frame": entry.get("frame"),
        "runtime_source": entry.get("source"),
        "runtime_checksum": entry.get("checksum"),
        "source_checksums": source_checksums,
    }


def _norm_opt(value: Any) -> Any:
    return normalize_checksum(value) if isinstance(value, str) else value


def build_id_envelope(
    included: list[dict[str, Any]],
    *,
    schema_version: str,
    generator_version: str,
    generator_config_version: str,
) -> dict[str, Any]:
    assets = sorted(
        (_envelope_asset(d) for d in included),
        key=lambda a: (str(a["asset_id"]), str(a["asset_version"])),
    )
    return {
        "schema_version": schema_version,
        "generator_version": generator_version,
        "generator_config_version": generator_config_version,
        "included_assets": assets,
    }


def compute_build_id(
    included: list[dict[str, Any]],
    *,
    schema_version: str,
    generator_version: str,
    generator_config_version: str,
) -> str:
    import hashlib

    envelope = build_id_envelope(
        included,
        schema_version=schema_version,
        generator_version=generator_version,
        generator_config_version=generator_config_version,
    )
    payload = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

"""Canonical serialization: metadata→manifest mapping, byte-stable form, build_id.

Single source of truth shared by the validator checks (C21/C22/C24) and the test
fixture builder, so the fixtures and the validator agree by construction. Implements
`production-asset-metadata-policy.md §9, §9a, §10`.
"""

from __future__ import annotations

import json
from typing import Any

from .core import normalize_checksum

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

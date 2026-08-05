"""Synthetic fixture builder for the ASSET-OPS-004 validator tests.

Materializes a complete, self-consistent workspace on disk (a *positive* fixture that
passes all 26 checks) plus mutators that break exactly one check to produce the
*negative* fixtures. Nothing here is a production asset: PNGs are generated in-memory,
checksums/build_id are derived with the validator's own canonical layer, and fixtures
are written to a caller-provided (tmp) directory — never under `assets/metadata/`.
"""

from __future__ import annotations

import copy
import json
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.asset_ops import canonical
from tools.asset_ops.core import sha256_hex

# ---------------------------------------------------------------------------
# Minimal deterministic PNG encoder (real, decodable; RGBA8, transparent fill).
# ---------------------------------------------------------------------------


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


def make_png(width: int, height: int) -> bytes:
    """A valid width x height RGBA PNG (fully transparent), byte-deterministic."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = bytearray()
    for _ in range(height):
        raw.append(0)  # filter type 0
        raw.extend(b"\x00\x00\x00\x00" * width)
    idat = zlib.compress(bytes(raw), 9)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _dumps(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Scenario model
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"
GENERATOR_VERSION = "1"
GENERATOR_CONFIG_VERSION = "1"
FUTURE = "2999-01-01T00:00:00+00:00"


@dataclass
class Scenario:
    records: dict[str, dict[str, Any]] = field(default_factory=dict)  # rel metadata path -> record
    binaries: dict[str, bytes] = field(default_factory=dict)  # ws-relative path -> bytes
    manifest: dict[str, Any] | None = None
    build_metadata: dict[str, Any] | None = None
    rollback_index: dict[str, Any] | None = None
    exceptions: dict[str, dict[str, Any]] = field(default_factory=dict)  # id -> record
    bundle_config: dict[str, Any] | None = None
    runtime_refs: list[str] | None = None
    category_fallbacks: dict[str, str] | None = None  # manifest categoryFallbacks (default valid)

    def clone(self) -> Scenario:
        return copy.deepcopy(self)

    def included(self) -> list[dict[str, Any]]:
        # Uses the SAME inclusion predicate as the validator — the fixture builder must
        # never carry its own inclusion rule (P2 corrections §2).
        return canonical.canonical_included_metadata(list(self.records.values()))

    def regenerate_derived(self) -> None:
        """TEST-ONLY workspace assembly helper — NOT the production generator.

        Recomputes a consistent manifest + build_id from the current records by calling
        the shared canonical primitives (`canonical_included_metadata`,
        `metadata_to_entry`, `compute_build_id`). This is **not** the official
        Metadata->Manifest API and **not** frontend runtime code; it exists only so a
        fixture stays internally consistent. When P3A lands the official Python
        `tools/asset_ops` generator, this helper will be replaced by a call to it.
        """
        incl = self.included()
        entries = [canonical.metadata_to_entry(r) for r in incl]
        catfb = (
            self.category_fallbacks
            if self.category_fallbacks is not None
            else {
                "building": "fallback.universal.primary",
                "ui": "fallback.universal.primary",
            }
        )
        self.manifest = {
            "manifestVersion": "1",
            "assets": entries,
            "categoryFallbacks": catfb,
        }
        self.build_metadata = {
            "schema_version": SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "generator_config_version": GENERATOR_CONFIG_VERSION,
            "build_id": canonical.compute_build_id(
                incl,
                schema_version=SCHEMA_VERSION,
                generator_version=GENERATOR_VERSION,
                generator_config_version=GENERATOR_CONFIG_VERSION,
            ),
        }

    def resync(self) -> None:
        """Rebuild runtime-refs + a single safe rollback candidate + derived artifacts.

        Keeps every check green except whatever the caller deliberately broke, so a
        negative fixture fails on exactly one code.
        """
        ids: list[str] = []
        for r in self.included():
            aid = r.get("asset_id")
            if isinstance(aid, str) and aid not in ids:
                ids.append(aid)
        self.runtime_refs = sorted(ids)
        self.rollback_index = {
            "candidates": [
                {
                    "manifest_version": "1",
                    "eligible": True,
                    "assets": [
                        {"asset_id": r["asset_id"], "asset_version": r["asset_version"]}
                        for r in self.included()  # only shipped (includable) assets
                    ],
                }
            ]
        }
        self.regenerate_derived()

    def add_image_asset(
        self,
        asset_id: str,
        category: str,
        *,
        anchor: dict[str, float] | None = None,
        fallback: str | None = None,
        approval_state: str = "APPROVED_FOR_PRODUCTION",
    ) -> None:
        """Add an extra image record (reusing the fallback.png binary). Test helper."""
        rec = _image_record(
            asset_id,
            category,
            "assets/source/fallback.png",
            sha256_hex(self.binaries["assets/source/fallback.png"]),
            anchor=anchor,
            fallback=fallback,
        )
        if approval_state != "APPROVED_FOR_PRODUCTION":
            rec["approval_state"] = approval_state
            rec["production_approved"] = False
        key = asset_id.replace(".", "-") + ".json"
        self.records[key] = rec

    def set_atlas_descriptor(self, descriptor: dict[str, Any], *, fix_checksum: bool) -> None:
        """Replace the atlas descriptor bytes; optionally refresh the JSON checksum."""
        data = _dumps(descriptor)
        self.binaries["assets/source/badge.json"] = data
        if fix_checksum:
            self.records["ui-incident-badge.json"]["source"]["atlas_json_checksum_sha256"] = (
                sha256_hex(data)
            )

    def write(self, root: Path) -> Path:
        for rel, data in self.binaries.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for rel, record in self.records.items():
            path = root / "assets" / "metadata" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_dumps(record))
        if self.manifest is not None:
            p = root / "assets" / "generated" / "manifests" / "manifest.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(canonical.canonical_manifest_bytes(self.manifest))
        if self.build_metadata is not None:
            p = root / "assets" / "generated" / "build-metadata.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(_dumps(self.build_metadata))
        if self.rollback_index is not None:
            p = root / "assets" / "releases" / "rollback-index.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(_dumps(self.rollback_index))
        for exc_id, exc in self.exceptions.items():
            p = root / "assets" / "approvals" / "exceptions" / f"{exc_id}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(_dumps(exc))
        if self.bundle_config is not None:
            (root / "bundle-config.json").write_bytes(_dumps(self.bundle_config))
        if self.runtime_refs is not None:
            (root / "runtime-refs.json").write_bytes(_dumps({"asset_ids": self.runtime_refs}))
        return root


def _approval(version: str) -> dict[str, Any]:
    return {
        "approval_state": "APPROVED_FOR_PRODUCTION",
        "reviewed_asset_version": version,
        "approval_scope": "production",
        "approved_by": "ops-lead",
        "approved_at": "2026-01-01T00:00:00+00:00",
        "rights_review_reference": "rights/RR-001",
        "technical_review_reference": "tech/TR-001",
        "review_notes": "reviewed",
    }


def _image_record(
    asset_id: str,
    category: str,
    source_path: str,
    checksum: str,
    *,
    anchor: dict[str, float] | None = None,
    footprint: dict[str, int] | None = None,
    fallback: str | None = None,
    bundle: str = "critical-core",
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "metadata_version": "1",
        "asset_id": asset_id,
        "asset_version": "1",
        "category": category,
        "source_type": "image",
        "source_path": source_path,
        "checksum_sha256": checksum,
        "bundle": bundle,
        "license_type": "company_owned",
        "license_reference": "internal/asset-register#1",
        "semantic_role": "building-structure",
        "approval_state": "APPROVED_FOR_PRODUCTION",
        "production_approved": True,
        "approval": _approval("1"),
    }
    if anchor is not None:
        rec["anchor"] = anchor
    if footprint is not None:
        rec["footprint"] = footprint
    if fallback is not None:
        rec["fallback_asset_id"] = fallback
    return rec


def image_only_scenario() -> Scenario:
    """A P3A generator workspace: image assets only (no atlas, which is BLOCKED_BY_P3B)."""
    s = base_scenario()
    del s.records["ui-incident-badge.json"]
    s.category_fallbacks = {
        "building": "fallback.universal.primary",
        "ui": "fallback.universal.primary",
    }
    s.runtime_refs = ["building.load-balancer.primary", "fallback.universal.primary"]
    s.regenerate_derived()
    return s


def write_generator_inputs(
    s: Scenario, root: Path, *, config: dict[str, Any] | None = None
) -> Path:
    """Write ONLY generator inputs (binaries + metadata + generator-config).

    The generated manifest / build-metadata / reports / rollback index are produced by
    `python -m tools.asset_ops generate` — not pre-written here.
    """
    for rel, data in s.binaries.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    for rel, rec in s.records.items():
        p = root / "assets" / "metadata" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(_dumps(rec))
    cfg = config or {
        "manifest_version": "1",
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "generator_config_version": GENERATOR_CONFIG_VERSION,
        "category_fallbacks": s.category_fallbacks or {},
    }
    (root / "assets" / "generator-config.json").write_bytes(_dumps(cfg))
    return root


def base_scenario() -> Scenario:
    """A complete positive fixture: 2 images + 1 atlas, all APPROVED and consistent."""
    s = Scenario()

    lb_png = make_png(128, 128)
    fb_png = make_png(64, 64)
    badge_png = make_png(64, 32)
    s.binaries["assets/source/load-balancer.png"] = lb_png
    s.binaries["assets/source/fallback.png"] = fb_png
    s.binaries["assets/source/badge.png"] = badge_png

    descriptor = {
        "image": "badge.png",
        "frames": {"badge-idle": {"frame": {"x": 0, "y": 0, "w": 64, "h": 32}}},
    }
    descriptor_bytes = _dumps(descriptor)
    s.binaries["assets/source/badge.json"] = descriptor_bytes

    s.records["fallback-universal.json"] = _image_record(
        "fallback.universal.primary",
        "fallback",
        "assets/source/fallback.png",
        sha256_hex(fb_png),
        anchor={"x": 0.5, "y": 0.5},
    )
    s.records["building-load-balancer.json"] = _image_record(
        "building.load-balancer.primary",
        "building",
        "assets/source/load-balancer.png",
        sha256_hex(lb_png),
        anchor={"x": 0.5, "y": 1.0},
        footprint={"width": 2, "height": 2},
        fallback="fallback.universal.primary",
    )
    atlas = {
        "schema_version": SCHEMA_VERSION,
        "metadata_version": "1",
        "asset_id": "ui.incident.badge",
        "asset_version": "1",
        "category": "ui",
        "source_type": "atlas",
        "source": {
            "type": "atlas",
            "atlas_json_path": "assets/source/badge.json",
            "atlas_image_path": "assets/source/badge.png",
            "atlas_json_checksum_sha256": sha256_hex(descriptor_bytes),
            "atlas_image_checksum_sha256": sha256_hex(badge_png),
            "frame": "badge-idle",
        },
        "anchor": {"x": 0.5, "y": 0.5},
        "bundle": "critical-core",
        "license_type": "company_owned",
        "license_reference": "internal/asset-register#2",
        "semantic_role": "status-indicator",
        "approval_state": "APPROVED_FOR_PRODUCTION",
        "production_approved": True,
        "approval": _approval("1"),
        "fallback_asset_id": "fallback.universal.primary",
    }
    s.records["ui-incident-badge.json"] = atlas

    s.bundle_config = {"critical_bundles": ["critical-core"], "bundle_dependencies": {}}
    s.runtime_refs = [
        "fallback.universal.primary",
        "building.load-balancer.primary",
        "ui.incident.badge",
    ]
    s.rollback_index = {
        "candidates": [
            {
                "manifest_version": "1",
                "eligible": True,
                "assets": [
                    {"asset_id": "fallback.universal.primary", "asset_version": "1"},
                    {"asset_id": "building.load-balancer.primary", "asset_version": "1"},
                    {"asset_id": "ui.incident.badge", "asset_version": "1"},
                ],
            }
        ]
    }
    s.regenerate_derived()
    return s

"""Python manifest generator + verify-generated (P3A §24).

The generator imports canonical.py primitives directly (no shadow inclusion rule) and
its output must pass the P2 validator (aligned by construction).
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.asset_ops import canonical, generator
from tools.asset_ops.cli import run
from tools.asset_ops.core import sha256_hex

from tests.assets.fixtures.builder import (
    GENERATOR_CONFIG_VERSION,
    GENERATOR_VERSION,
    SCHEMA_VERSION,
    Scenario,
    _image_record,
    image_only_scenario,
    make_png,
    write_generator_inputs,
)

FB_BYTES = image_only_scenario().binaries["assets/source/fallback.png"]


def _add_image(s: Scenario, asset_id: str, state: str) -> None:
    rec = _image_record(
        asset_id,
        "tile",
        "assets/source/fallback.png",
        sha256_hex(FB_BYTES),
        anchor={"x": 0.5, "y": 0.5},
    )
    if state != "APPROVED_FOR_PRODUCTION":
        rec["approval_state"] = state
        rec["production_approved"] = False
    s.records[asset_id.replace(".", "-") + ".json"] = rec


def _ws(tmp_path: Path, name: str = "gen") -> Path:
    s = image_only_scenario()
    return write_generator_inputs(s, tmp_path / name)


def test_generate_output_passes_p2_validator(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    assert run(["generate", "--workspace", str(root), "--quiet"]) == 0
    # generated output must pass the enforced gate (aligned by construction)
    assert (
        run(["validate", "--workspace", str(root), "--quiet", "--report", str(tmp_path / "r.json")])
        == 0
    )
    rep = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert rep["status"] == "pass"
    assert run(["verify-generated", "--workspace", str(root), "--quiet"]) == 0


def test_no_shadow_inclusion_rule() -> None:
    # The generator's inclusion set is exactly canonical's — proving it delegates.
    s = image_only_scenario()
    records = list(s.records.values())
    out = generator.build_outputs(
        records,
        {
            "manifest_version": "1",
            "schema_version": SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "generator_config_version": GENERATOR_CONFIG_VERSION,
            "category_fallbacks": s.category_fallbacks,
        },
    )
    manifest_ids = {e["assetId"] for e in out.manifest["assets"]}
    canonical_ids = {d["asset_id"] for d in canonical.canonical_included_metadata(records)}
    assert manifest_ids == canonical_ids


def test_image_entry_and_category_mapping(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    run(["generate", "--workspace", str(root), "--quiet"])
    manifest = json.loads((root / "assets/generated/manifests/manifest.json").read_text("utf-8"))
    building = next(
        e for e in manifest["assets"] if e["assetId"] == "building.load-balancer.primary"
    )
    assert building["category"] == "building"  # category not inferred
    assert building["sourceType"] == "image"
    assert building["source"] == "assets/source/load-balancer.png"  # source_path -> source
    assert len(building["checksum"]) == 64  # checksum_sha256 -> checksum
    assert building["fallbackAssetId"] == "fallback.universal.primary"
    # governance never leaks
    for leaked in ("approval_state", "production_approved", "approved_by", "license_type"):
        assert leaked not in building


def test_category_fallbacks_emitted_and_valid(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    run(["generate", "--workspace", str(root), "--quiet"])
    manifest = json.loads((root / "assets/generated/manifests/manifest.json").read_text("utf-8"))
    assert manifest["categoryFallbacks"]["building"] == "fallback.universal.primary"
    # P2 C09 accepts it
    assert run(["validate", "--workspace", str(root), "--quiet"]) == 0


def test_draft_is_blocking_exclusion(tmp_path: Path) -> None:
    s = image_only_scenario()
    _add_image(s, "tile.draft.primary", "DRAFT")
    root = write_generator_inputs(s, tmp_path / "draft")
    assert run(["generate", "--workspace", str(root), "--quiet"]) == 1
    excl = json.loads((root / "assets/generated/reports/exclusion-report.json").read_text("utf-8"))
    entry = next(e for e in excl["exclusions"] if e["asset_id"] == "tile.draft.primary")
    assert entry["exclusion_reason_code"] == "NOT_PRODUCTION_APPROVED"
    assert entry["merge_blocking"] is True


def test_deprecated_is_soft_exclusion(tmp_path: Path) -> None:
    s = image_only_scenario()
    _add_image(s, "tile.legacy.primary", "DEPRECATED")
    root = write_generator_inputs(s, tmp_path / "dep")
    assert run(["generate", "--workspace", str(root), "--quiet"]) == 0  # soft: not blocking
    excl = json.loads((root / "assets/generated/reports/exclusion-report.json").read_text("utf-8"))
    entry = next(e for e in excl["exclusions"] if e["asset_id"] == "tile.legacy.primary")
    assert entry["exclusion_reason_code"] == "DEPRECATED"
    assert entry["merge_blocking"] is False


def test_revoked_is_hard_error(tmp_path: Path) -> None:
    s = image_only_scenario()
    _add_image(s, "tile.revoked.primary", "REVOKED")
    root = write_generator_inputs(s, tmp_path / "rev")
    assert run(["generate", "--workspace", str(root), "--quiet"]) == 1
    excl = json.loads((root / "assets/generated/reports/exclusion-report.json").read_text("utf-8"))
    entry = next(e for e in excl["exclusions"] if e["asset_id"] == "tile.revoked.primary")
    assert entry["exclusion_reason_code"] == "REVOKED"
    assert entry["merge_blocking"] is True


def test_approval_state_mismatch_is_hard_error(tmp_path: Path) -> None:
    s = image_only_scenario()
    s.records["building-load-balancer.json"]["production_approved"] = False  # APPROVED + false
    root = write_generator_inputs(s, tmp_path / "mm")
    assert run(["generate", "--workspace", str(root), "--quiet"]) == 1


def test_missing_and_excluded_category_fallback_target(tmp_path: Path) -> None:
    s = image_only_scenario()
    s.category_fallbacks = {"building": "no.such.asset"}
    root = write_generator_inputs(s, tmp_path / "missfb")
    assert run(["generate", "--workspace", str(root), "--quiet"]) == 1


def test_deterministic_bytes_and_build_id_stability(tmp_path: Path) -> None:
    r1, r2 = _ws(tmp_path, "d1"), _ws(tmp_path, "d2")
    run(["generate", "--workspace", str(r1), "--quiet"])
    run(["generate", "--workspace", str(r2), "--quiet"])
    for rel in (
        "assets/generated/manifests/manifest.json",
        "assets/generated/build-metadata.json",
        "assets/generated/reports/mapping-report.json",
        "assets/generated/reports/exclusion-report.json",
    ):
        assert (r1 / rel).read_bytes() == (r2 / rel).read_bytes(), rel


def test_build_id_changes_on_binary_checksum_change(tmp_path: Path) -> None:
    root = _ws(tmp_path, "b1")
    run(["generate", "--workspace", str(root), "--quiet"])
    bid1 = json.loads((root / "assets/generated/build-metadata.json").read_text("utf-8"))[
        "build_id"
    ]
    # change the building binary (and its declared checksum)
    s = image_only_scenario()
    png = make_png(130, 130)
    s.binaries["assets/source/load-balancer.png"] = png
    s.records["building-load-balancer.json"]["checksum_sha256"] = sha256_hex(png)
    root2 = write_generator_inputs(s, tmp_path / "b2")
    run(["generate", "--workspace", str(root2), "--quiet"])
    bid2 = json.loads((root2 / "assets/generated/build-metadata.json").read_text("utf-8"))[
        "build_id"
    ]
    assert bid1 != bid2


def test_verify_generated_detects_drift(tmp_path: Path) -> None:
    root = _ws(tmp_path, "drift")
    run(["generate", "--workspace", str(root), "--quiet"])
    assert run(["verify-generated", "--workspace", str(root), "--quiet"]) == 0
    manifest = root / "assets/generated/manifests/manifest.json"
    manifest.write_bytes(
        manifest.read_bytes().replace(b'"manifestVersion": "1"', b'"manifestVersion": "7"')
    )
    assert run(["verify-generated", "--workspace", str(root), "--quiet"]) == 1


def test_atlas_asset_blocked_by_p3b(tmp_path: Path) -> None:
    # An approved atlas asset is NOT runtime-ready in P3A -> generation hard-errors.
    from tests.assets.fixtures.builder import base_scenario

    s = base_scenario()  # has an atlas asset
    s.category_fallbacks = {"building": "fallback.universal.primary"}
    root = write_generator_inputs(s, tmp_path / "atlas")
    assert run(["generate", "--workspace", str(root), "--quiet"]) == 1
    summ = json.loads(
        (root / "assets/generated/reports/validation-summary.json").read_text("utf-8")
    )
    assert any("atlas" in m.lower() or "BLOCKED_BY_P3B" in m for m in summ["hard_error_messages"])

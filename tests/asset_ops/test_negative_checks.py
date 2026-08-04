"""One targeted negative fixture per contract check (C01-C26).

Each mutator breaks exactly one thing on the positive `base_scenario`; the validator
must fail (exit 1) and emit the exact error code for that check. `isolated=True` cases
additionally assert no *other* merge-blocking check fired.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path

from tools.asset_ops.core import sha256_hex

from tests.asset_ops._helpers import blocking_checks, blocking_codes, run_scenario
from tests.assets.fixtures.builder import Scenario, base_scenario, make_png

BUILDING = "building-load-balancer.json"
BADGE = "ui-incident-badge.json"
BUILDING_ID = "building.load-balancer.primary"


def _set_building_image(s: Scenario, width: int, height: int) -> None:
    png = make_png(width, height)
    s.binaries["assets/source/load-balancer.png"] = png
    s.records[BUILDING]["checksum_sha256"] = sha256_hex(png)


def _image_record(asset_id: str, category: str, fallback: str | None = None) -> dict[str, object]:
    from tests.assets.fixtures.builder import _image_record as build_image_record  # noqa: PLC0415

    fb_bytes = base_scenario().binaries["assets/source/fallback.png"]
    return build_image_record(
        asset_id, category, "assets/source/fallback.png", sha256_hex(fb_bytes),
        anchor={"x": 0.5, "y": 0.5}, fallback=fallback,
    )


# ---- mutators --------------------------------------------------------------

def m_c01(s: Scenario) -> None:
    s.records[BUILDING]["category"] = "widget"
    s.resync()


def m_c02(s: Scenario) -> None:
    s.records["building-dup.json"] = copy.deepcopy(s.records[BUILDING])
    s.resync()


def m_c03(s: Scenario) -> None:
    twin = copy.deepcopy(s.records[BADGE])
    twin["asset_id"] = "ui.incident.badge2"
    twin["approval"]["reviewed_asset_version"] = twin["asset_version"]
    s.records["ui-incident-badge2.json"] = twin  # same atlas_json_path + frame
    s.resync()


def m_c04(s: Scenario) -> None:
    s.records[BUILDING]["source_path"] = "assets/source/missing.png"
    s.resync()


def m_c05(s: Scenario) -> None:
    s.set_atlas_descriptor(
        {
            "image": "badge.png",
            "frames": {"badge-idle": {"frame": {"x": 0, "y": 0, "w": 999, "h": 32}}},
        },
        fix_checksum=True,
    )
    s.resync()


def m_c06(s: Scenario) -> None:
    s.records[BADGE]["source"]["frame"] = "BadFrame"
    s.set_atlas_descriptor(
        {
            "image": "badge.png",
            "frames": {"BadFrame": {"frame": {"x": 0, "y": 0, "w": 64, "h": 32}}},
        },
        fix_checksum=True,
    )
    s.resync()


def m_c07(s: Scenario) -> None:
    s.records[BUILDING]["anchor"] = {"x": 1.5, "y": 1.0}
    s.resync()


def m_c08(s: Scenario) -> None:
    s.records[BUILDING]["footprint"] = {"width": 9, "height": 2}
    s.resync()


def m_c09(s: Scenario) -> None:
    s.records[BUILDING]["fallback_asset_id"] = "ghost.asset.primary"
    s.resync()


def m_c10(s: Scenario) -> None:
    s.records["building-a.json"] = _image_record("building.a.primary", "tile", fallback=BUILDING_ID)
    s.records[BUILDING]["fallback_asset_id"] = "building.a.primary"
    s.resync()


def m_c11(s: Scenario) -> None:
    chain = [f"building.f{n}.primary" for n in range(1, 5)]  # 4 hops > 3-hop max
    s.records[BUILDING]["fallback_asset_id"] = chain[0]
    for i, aid in enumerate(chain):
        nxt = chain[i + 1] if i + 1 < len(chain) else None
        s.records[f"building-f{i + 1}.json"] = _image_record(aid, "tile", fallback=nxt)
    s.resync()


def m_c12(s: Scenario) -> None:
    s.records[BUILDING]["checksum_sha256"] = "a" * 64
    s.resync()


def m_c13(s: Scenario) -> None:
    s.records[BUILDING]["license_type"] = "unknown"
    s.resync()


def m_c14(s: Scenario) -> None:
    s.records[BUILDING]["approval"]["reviewed_asset_version"] = "99"
    s.resync()


def m_c15(s: Scenario) -> None:
    _set_building_image(s, 4097, 8)  # > 4096 hard-max, tiny GPU footprint
    s.resync()


def m_c16(s: Scenario) -> None:
    png = make_png(5000, 64)  # > 4096, frame still in bounds, small GPU
    s.binaries["assets/source/badge.png"] = png
    s.records[BADGE]["source"]["atlas_image_checksum_sha256"] = sha256_hex(png)
    s.resync()


def m_c17(s: Scenario) -> None:
    blob = bytes(9_000_000)  # > 8 MiB critical transfer budget
    s.binaries["assets/source/big.bin"] = blob
    rec = _image_record("building.big.primary", "tile")
    rec["source_path"] = "assets/source/big.bin"
    rec["checksum_sha256"] = sha256_hex(blob)
    s.records["building-big.json"] = rec
    s.resync()


def m_c18(s: Scenario) -> None:
    _set_building_image(s, 4096, 4096)  # 64 MiB * 1.333 mip -> > resident budget
    s.records[BUILDING]["mipmap"] = True
    s.resync()


def m_c20(s: Scenario) -> None:
    s.resync()
    assert s.runtime_refs is not None
    s.runtime_refs = [*s.runtime_refs, "building.ghost.primary"]


def m_c21(s: Scenario) -> None:
    assert s.manifest is not None
    for entry in s.manifest["assets"]:
        if entry["assetId"] == BUILDING_ID:
            entry["checksum"] = "d" * 64


def m_c23(s: Scenario) -> None:
    assert s.bundle_config is not None
    s.bundle_config["bundle_dependencies"] = {"a": ["b"], "b": ["a"]}


def m_c24(s: Scenario) -> None:
    assert s.build_metadata is not None
    s.build_metadata["build_id"] = "0" * 64


def m_c25(s: Scenario) -> None:
    s.rollback_index = None


def m_c26(s: Scenario) -> None:
    for v in ("2", "3", "4"):
        rec = copy.deepcopy(s.records[BUILDING])
        rec["asset_version"] = v
        rec["approval"]["reviewed_asset_version"] = v
        s.records[f"building-v{v}.json"] = rec
    s.resync()


# (mutator, expected_check, expected_code, isolated)
CASES: list[tuple[str, Callable[[Scenario], None], str, str, bool]] = [
    ("C01", m_c01, "C01", "SCHEMA_INVALID", True),
    ("C02", m_c02, "C02", "DUP_ASSET_VERSION", True),
    ("C03", m_c03, "C03", "DUP_FRAME", True),
    ("C04", m_c04, "C04", "SOURCE_MISSING", True),
    ("C05", m_c05, "C05", "ATLAS_INCONSISTENT", True),
    ("C06", m_c06, "C06", "FRAME_NAME_INVALID", True),
    ("C07", m_c07, "C07", "ANCHOR_RANGE", True),
    ("C08", m_c08, "C08", "FOOTPRINT_RANGE", True),
    ("C09", m_c09, "C09", "FALLBACK_MISSING", True),
    ("C10", m_c10, "C10", "FALLBACK_CYCLE", True),
    ("C11", m_c11, "C11", "FALLBACK_DEPTH", True),
    ("C12", m_c12, "C12", "ASSET_CHECKSUM_IMAGE_MISMATCH", True),
    ("C13", m_c13, "C13", "LICENSE_INVALID", True),
    ("C14", m_c14, "C14", "APPROVAL_INVALID", True),
    ("C15", m_c15, "C15", "TEXTURE_DIMENSION", True),
    ("C16", m_c16, "C16", "ATLAS_DIMENSION", True),
    ("C17", m_c17, "C17", "BUNDLE_SIZE", True),
    ("C18", m_c18, "C18", "GPU_MEMORY", True),
    ("C20", m_c20, "C20", "UNMANIFESTED_ASSET", True),
    ("C21", m_c21, "C21", "MAPPING_MISMATCH", True),
    ("C23", m_c23, "C23", "BUNDLE_CYCLE", True),
    ("C24", m_c24, "C24", "BUILD_ID_MISMATCH", True),
    ("C25", m_c25, "C25", "ROLLBACK_MISSING", True),
    ("C26", m_c26, "C26", "STALE_RETENTION", True),
]


def test_each_check_has_a_failing_fixture(tmp_path: Path) -> None:
    failures: list[str] = []
    for name, mutate, check, code, isolated in CASES:
        scn = base_scenario()
        mutate(scn)
        rc, report = run_scenario(scn, tmp_path, name=name)
        b_codes = blocking_codes(report)
        b_checks = blocking_checks(report)
        if rc != 1:
            failures.append(f"{name}: expected exit 1, got {rc}")
        if report["status"] != "fail":
            failures.append(f"{name}: expected status fail, got {report['status']}")
        if code not in b_codes:
            failures.append(f"{name}: expected code {code}, got blocking codes {sorted(b_codes)}")
        if check not in b_checks:
            failures.append(f"{name}: expected check {check} to block, got {sorted(b_checks)}")
        if isolated and b_checks != {check}:
            failures.append(f"{name}: expected ONLY {check} to block, got {sorted(b_checks)}")
    assert not failures, "\n".join(failures)


def test_c22_nondeterministic_manifest(tmp_path: Path) -> None:
    root = tmp_path / "c22"
    root.mkdir(parents=True, exist_ok=True)
    base_scenario().write(root)
    manifest_path = root / "assets" / "generated" / "manifests" / "manifest.json"
    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Re-serialize in a non-canonical form (unsorted keys, 4-space indent).
    manifest_path.write_text(json.dumps(parsed, indent=4), encoding="utf-8")
    from tests.asset_ops._helpers import run_ws  # noqa: PLC0415

    rc, report = run_ws(root, tmp_path / "c22-report.json")
    assert rc == 1
    assert "NONDETERMINISTIC" in blocking_codes(report)
    assert blocking_checks(report) == {"C22"}

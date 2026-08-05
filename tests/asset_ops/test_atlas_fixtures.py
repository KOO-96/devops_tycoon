"""The 8 atlas-independent negative fixtures (no atlas *loader* needed — ATLAS_LOADER_CASE_B).

These exercise the metadata/descriptor/checksum/bounds contract (C04/C05/C12) that the
validator enforces offline, with no Pixi Spritesheet or real atlas runtime involved.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tools.asset_ops.core import sha256_hex

from tests.asset_ops._helpers import blocking_codes, run_scenario
from tests.assets.fixtures.builder import Scenario, base_scenario, make_png

BADGE = "ui-incident-badge.json"


def _frame(w: int, h: int) -> dict[str, object]:
    return {
        "image": "badge.png",
        "frames": {"badge-idle": {"frame": {"x": 0, "y": 0, "w": w, "h": h}}},
    }


def a_missing_json(s: Scenario) -> None:
    s.records[BADGE]["source"]["atlas_json_path"] = "assets/source/missing.json"
    s.resync()


def a_missing_image(s: Scenario) -> None:
    s.records[BADGE]["source"]["atlas_image_path"] = "assets/source/missing.png"
    s.set_atlas_descriptor(
        {"image": "missing.png", "frames": _frame(64, 32)["frames"]}, fix_checksum=True
    )
    s.resync()


def a_json_checksum(s: Scenario) -> None:
    s.records[BADGE]["source"]["atlas_json_checksum_sha256"] = "b" * 64
    s.resync()


def a_image_checksum(s: Scenario) -> None:
    s.records[BADGE]["source"]["atlas_image_checksum_sha256"] = "c" * 64
    s.resync()


def a_image_reference(s: Scenario) -> None:
    s.set_atlas_descriptor(
        {"image": "other.png", "frames": _frame(64, 32)["frames"]}, fix_checksum=True
    )
    s.resync()


def a_duplicate_frame(s: Scenario) -> None:
    s.set_atlas_descriptor(
        {
            "image": "badge.png",
            "frames": [
                {"name": "badge-idle", "frame": {"x": 0, "y": 0, "w": 64, "h": 32}},
                {"name": "badge-idle", "frame": {"x": 0, "y": 0, "w": 64, "h": 32}},
            ],
        },
        fix_checksum=True,
    )
    s.resync()


def a_frame_out_of_bounds(s: Scenario) -> None:
    s.set_atlas_descriptor(_frame(999, 32), fix_checksum=True)
    s.resync()


def a_metadata_frame_missing(s: Scenario) -> None:
    s.set_atlas_descriptor(
        {
            "image": "badge.png",
            "frames": {"other-frame": {"frame": {"x": 0, "y": 0, "w": 64, "h": 32}}},
        },
        fix_checksum=True,
    )
    s.resync()


CASES: list[tuple[str, Callable[[Scenario], None], str]] = [
    ("missing_json", a_missing_json, "ATLAS_INCONSISTENT"),
    ("missing_image", a_missing_image, "SOURCE_MISSING"),
    ("json_checksum_mismatch", a_json_checksum, "ASSET_CHECKSUM_ATLAS_JSON_MISMATCH"),
    ("image_checksum_mismatch", a_image_checksum, "ASSET_CHECKSUM_ATLAS_IMAGE_MISMATCH"),
    ("image_reference_mismatch", a_image_reference, "ASSET_ATLAS_IMAGE_REFERENCE_MISMATCH"),
    ("duplicate_frame", a_duplicate_frame, "ATLAS_INCONSISTENT"),
    ("frame_out_of_bounds", a_frame_out_of_bounds, "ATLAS_INCONSISTENT"),
    ("metadata_frame_missing", a_metadata_frame_missing, "ATLAS_INCONSISTENT"),
]


def test_atlas_independent_negative_fixtures(tmp_path: Path) -> None:
    failures: list[str] = []
    for name, mutate, code in CASES:
        scn = base_scenario()
        mutate(scn)
        rc, report = run_scenario(scn, tmp_path, name=name)
        if rc != 1:
            failures.append(f"{name}: expected exit 1, got {rc}")
        if code not in blocking_codes(report):
            failures.append(f"{name}: expected {code}, got {sorted(blocking_codes(report))}")
    assert not failures, "\n".join(failures)


def test_image_checksum_detects_tampered_bytes(tmp_path: Path) -> None:
    scn = base_scenario()
    # keep declared checksum, replace the badge image bytes with a different valid PNG
    scn.binaries["assets/source/badge.png"] = make_png(64, 32) + b"\x00tamper"
    rc, report = run_scenario(scn, tmp_path, name="tamper")
    assert rc == 1
    assert "ASSET_CHECKSUM_ATLAS_IMAGE_MISMATCH" in blocking_codes(report)
    assert (
        sha256_hex(scn.binaries["assets/source/badge.png"])
        != scn.records[BADGE]["source"]["atlas_image_checksum_sha256"]
    )

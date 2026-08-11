"""P4 Image Dry-run — Python end-to-end over a SYNTHETIC (non-production) workspace.

Metadata -> generate -> verify-generated -> P2 validate, then failure injections A-D
(checksum, manifest drift, approval, missing source) each block the pipeline, and a fix
restores PASS. No production assets/metadata; the workspace lives in tmp only.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.asset_ops.cli import run
from tools.asset_ops.core import sha256_hex

from tests.assets.fixtures.builder import image_only_scenario, make_png, write_generator_inputs

DRYRUN = "dryrun"


def _dryrun_ws(tmp_path: Path, name: str = DRYRUN) -> Path:
    # image_only_scenario is entirely synthetic (in-memory PNGs, no production paths).
    return write_generator_inputs(image_only_scenario(), tmp_path / name)


def test_p4_happy_path_generate_verify_validate(tmp_path: Path) -> None:
    root = _dryrun_ws(tmp_path)
    assert run(["generate", "--workspace", str(root), "--quiet"]) == 0
    assert run(["verify-generated", "--workspace", str(root), "--quiet"]) == 0
    assert (
        run(["validate", "--workspace", str(root), "--quiet", "--report", str(tmp_path / "r.json")])
        == 0
    )
    rep = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert rep["status"] == "pass"
    manifest = json.loads((root / "assets/generated/manifests/manifest.json").read_text("utf-8"))
    img = next(e for e in manifest["assets"] if e["sourceType"] == "image")
    assert img["source"] and len(img["checksum"]) == 64
    for gov in ("approval_state", "production_approved", "license_type", "approved_by"):
        assert gov not in img  # governance never in the runtime manifest


def test_p4_failure_A_checksum_mismatch(tmp_path: Path) -> None:
    s = image_only_scenario()
    s.records["building-load-balancer.json"]["checksum_sha256"] = "0" * 64  # metadata lies
    root = write_generator_inputs(s, tmp_path / "A")
    run(["generate", "--workspace", str(root), "--quiet"])  # bakes the bad checksum in
    rc = run(
        ["validate", "--workspace", str(root), "--quiet", "--report", str(tmp_path / "a.json")]
    )
    rep = json.loads((tmp_path / "a.json").read_text(encoding="utf-8"))
    assert rc == 1
    assert any(r["code"] == "ASSET_CHECKSUM_IMAGE_MISMATCH" for r in rep["results"])


def test_p4_failure_B_manifest_drift_blocks_then_recovers(tmp_path: Path) -> None:
    root = _dryrun_ws(tmp_path, "B")
    run(["generate", "--workspace", str(root), "--quiet"])
    assert run(["verify-generated", "--workspace", str(root), "--quiet"]) == 0
    m = root / "assets/generated/manifests/manifest.json"
    m.write_bytes(m.read_bytes().replace(b'"manifestVersion": "1"', b'"manifestVersion": "999"'))
    assert run(["verify-generated", "--workspace", str(root), "--quiet"]) == 1  # BLOCKED
    run(["generate", "--workspace", str(root), "--quiet"])  # regenerate = fix
    assert run(["verify-generated", "--workspace", str(root), "--quiet"]) == 0  # RECOVERED


def test_p4_failure_C_draft_approval(tmp_path: Path) -> None:
    s = image_only_scenario()
    s.records["building-load-balancer.json"]["approval_state"] = "DRAFT"
    s.records["building-load-balancer.json"]["production_approved"] = False
    root = write_generator_inputs(s, tmp_path / "C")
    assert run(["generate", "--workspace", str(root), "--quiet"]) == 1
    excl = json.loads((root / "assets/generated/reports/exclusion-report.json").read_text("utf-8"))
    e = next(x for x in excl["exclusions"] if x["asset_id"] == "building.load-balancer.primary")
    assert e["exclusion_reason_code"] == "NOT_PRODUCTION_APPROVED" and e["merge_blocking"] is True
    manifest = json.loads((root / "assets/generated/manifests/manifest.json").read_text("utf-8"))
    assert all(a["assetId"] != "building.load-balancer.primary" for a in manifest["assets"])
    # recover
    s.records["building-load-balancer.json"]["approval_state"] = "APPROVED_FOR_PRODUCTION"
    s.records["building-load-balancer.json"]["production_approved"] = True
    root2 = write_generator_inputs(s, tmp_path / "C2")
    assert run(["generate", "--workspace", str(root2), "--quiet"]) == 0


def test_p4_failure_D_missing_source(tmp_path: Path) -> None:
    root = _dryrun_ws(tmp_path, "D")
    run(["generate", "--workspace", str(root), "--quiet"])
    (root / "assets/source/load-balancer.png").unlink()  # source disappears
    rc = run(
        ["validate", "--workspace", str(root), "--quiet", "--report", str(tmp_path / "d.json")]
    )
    rep = json.loads((tmp_path / "d.json").read_text(encoding="utf-8"))
    assert rc == 1
    assert any(r["code"] == "SOURCE_MISSING" for r in rep["results"])  # not silently passed


def test_p4_build_id_deterministic_across_roots(tmp_path: Path) -> None:
    r1, r2 = _dryrun_ws(tmp_path, "det1"), _dryrun_ws(tmp_path, "det2")
    run(["generate", "--workspace", str(r1), "--quiet"])
    run(["generate", "--workspace", str(r2), "--quiet"])
    b1 = json.loads((r1 / "assets/generated/build-metadata.json").read_text("utf-8"))["build_id"]
    b2 = json.loads((r2 / "assets/generated/build-metadata.json").read_text("utf-8"))["build_id"]
    assert b1 == b2
    # a changed approved binary flips build_id (integrity is real)
    s = image_only_scenario()
    png = make_png(70, 70)
    s.binaries["assets/source/load-balancer.png"] = png
    s.records["building-load-balancer.json"]["checksum_sha256"] = sha256_hex(png)
    r3 = write_generator_inputs(s, tmp_path / "det3")
    run(["generate", "--workspace", str(r3), "--quiet"])
    b3 = json.loads((r3 / "assets/generated/build-metadata.json").read_text("utf-8"))["build_id"]
    assert b3 != b1

"""SYNTHETIC do-not-merge P4 gate probe (§20/§23): makes asset-production-gate FAIL to
prove Branch Protection blocks the merge on a pipeline failure; removed to show recovery."""

from __future__ import annotations

from pathlib import Path

from tests.assets.fixtures.builder import image_only_scenario, write_generator_inputs
from tools.asset_ops.cli import run


def test_p4_gate_probe(tmp_path: Path) -> None:
    root = write_generator_inputs(image_only_scenario(), tmp_path / "probe")
    run(["generate", "--workspace", str(root), "--quiet"])
    m = root / "assets/generated/manifests/manifest.json"
    m.write_bytes(m.read_bytes().replace(b'"manifestVersion": "1"', b'"manifestVersion": "42"'))
    rc = run(["verify-generated", "--workspace", str(root), "--quiet"])
    # Inverted on purpose: verify-generated correctly returns 1 on drift, failing this check.
    assert rc == 0, f"P4 probe: verify-generated blocked drift (rc={rc}) as expected"

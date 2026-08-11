"""P4 harness prep: build a SYNTHETIC workspace, run the REAL generator + verify + P2
validator, then stage the generator-produced manifest + synthetic PNGs for the browser
to consume over real HTTP. No production assets. Output dir is served by Vite."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tests.assets.fixtures.builder import image_only_scenario, write_generator_inputs  # noqa: E402
from tools.asset_ops.cli import run  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1])
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    ws = Path(tempfile.mkdtemp())
    scenario = image_only_scenario()
    write_generator_inputs(scenario, ws)

    assert run(["generate", "--workspace", str(ws), "--quiet"]) == 0, "generate failed"
    assert run(["verify-generated", "--workspace", str(ws), "--quiet"]) == 0, (
        "verify-generated failed"
    )
    assert run(["validate", "--workspace", str(ws), "--quiet"]) == 0, "P2 validate failed"

    manifest_path = ws / "assets" / "generated" / "manifests" / "manifest.json"
    shutil.copy(manifest_path, out / "manifest.json")
    for rel in scenario.binaries:  # preserve the manifest `source` relative paths
        src = ws / rel
        if src.is_file() and rel.endswith(".png"):
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "assets": [
                    {"assetId": a["assetId"], "source": a["source"], "checksum": a["checksum"]}
                    for a in manifest["assets"]
                ]
            }
        )
    )


if __name__ == "__main__":
    main()

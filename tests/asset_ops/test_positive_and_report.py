"""Positive fixture, deterministic report, and report-schema/contract assertions."""

from __future__ import annotations

import json
from pathlib import Path

from tools.asset_ops.checks import CHECKS
from tools.asset_ops.core import REQUIRED_CHECK

from tests.asset_ops._helpers import run_scenario, run_ws
from tests.assets.fixtures.builder import base_scenario


def test_positive_fixture_passes_all_checks(tmp_path: Path) -> None:
    rc, report = run_scenario(base_scenario(), tmp_path)
    assert rc == 0
    assert report["status"] == "pass"
    assert report["summary"]["errors"] == 0
    assert report["summary"]["failed_checks"] == 0
    assert report["summary"]["passed_checks"] == len(CHECKS) == 26
    assert report["results"] == []
    assert report["required_check"] == REQUIRED_CHECK == "asset-production-gate"
    assert isinstance(report["build_id"], str) and len(report["build_id"]) == 64


def test_report_has_contract_shape(tmp_path: Path) -> None:
    _, report = run_scenario(base_scenario(), tmp_path)
    for key in (
        "schema_version",
        "tool_version",
        "required_check",
        "build_id",
        "status",
        "summary",
        "results",
    ):
        assert key in report, f"missing top-level key {key}"
    for key in ("errors", "warnings", "excluded", "passed_checks", "failed_checks"):
        assert key in report["summary"], f"missing summary key {key}"


def test_report_is_byte_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "det"
    root.mkdir(parents=True, exist_ok=True)
    base_scenario().write(root)
    run_ws(root, tmp_path / "r1.json")
    run_ws(root, tmp_path / "r2.json")
    assert (tmp_path / "r1.json").read_bytes() == (tmp_path / "r2.json").read_bytes()


def test_report_has_no_absolute_paths_or_pii(tmp_path: Path) -> None:
    # Break several checks so results are populated, then scan for leaked host paths.
    scn = base_scenario()
    scn.records["building-load-balancer.json"]["anchor"] = {"x": 5.0, "y": 9.0}
    scn.resync()
    root = tmp_path / "leak"
    root.mkdir(parents=True, exist_ok=True)
    scn.write(root)
    report_path = tmp_path / "leak-report.json"
    run_ws(root, report_path)
    text = report_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in text, "report leaked the absolute workspace path"
    report = json.loads(text)
    assert report["results"], "expected populated results for this assertion"
    for r in report["results"]:
        ap = r["artifact_path"]
        assert ap is None or not ap.startswith("/"), f"absolute artifact_path leaked: {ap}"


def test_all_26_checks_registered() -> None:
    assert sorted(CHECKS) == [f"C{n:02d}" for n in range(1, 27)]

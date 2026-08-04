"""CLI contract: exit codes 0/1/2/3, report emission, --now handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tools.asset_ops import cli
from tools.asset_ops.cli import run

from tests.assets.fixtures.builder import base_scenario


def test_exit_2_on_bad_usage() -> None:
    assert run(["validate"]) == 2  # missing required --workspace
    assert run([]) == 2  # missing subcommand


def test_exit_2_on_missing_workspace(tmp_path: Path) -> None:
    report_path = tmp_path / "r.json"
    rc = run(["validate", "--workspace", str(tmp_path / "nope"),
              "--report", str(report_path), "--quiet"])
    assert rc == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "error"
    assert report["error"]["kind"] == "input"


def test_exit_2_on_invalid_now(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir(parents=True, exist_ok=True)
    base_scenario().write(root)
    rc = run(["validate", "--workspace", str(root), "--now", "not-a-date", "--quiet"])
    assert rc == 2


def test_exit_3_on_internal_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "ws"
    root.mkdir(parents=True, exist_ok=True)
    base_scenario().write(root)

    def boom(_ctx: object) -> list[object]:
        raise RuntimeError("synthetic internal failure")

    monkeypatch.setattr(cli, "run_all", boom)
    report_path = tmp_path / "r.json"
    rc = run(["validate", "--workspace", str(root), "--report", str(report_path), "--quiet"])
    assert rc == 3
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "error"
    assert report["error"]["kind"] == "error"


def test_report_written_and_parseable(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir(parents=True, exist_ok=True)
    base_scenario().write(root)
    report_path = tmp_path / "nested" / "report.json"
    rc = run(["validate", "--workspace", str(root), "--report", str(report_path), "--quiet"])
    assert rc == 0
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["required_check"] == "asset-production-gate"

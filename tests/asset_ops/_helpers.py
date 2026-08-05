"""Shared helpers for the asset-production-gate validator tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.asset_ops.cli import run

from tests.assets.fixtures.builder import Scenario

DEFAULT_NOW = "2026-06-01T00:00:00+00:00"


def run_ws(root: Path, report_path: Path, now: str = DEFAULT_NOW) -> tuple[int, dict[str, Any]]:
    rc = run(
        [
            "validate",
            "--workspace",
            str(root),
            "--report",
            str(report_path),
            "--now",
            now,
            "--quiet",
        ]
    )
    report: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    return rc, report


def run_scenario(
    scn: Scenario, tmp_path: Path, name: str = "ws", now: str = DEFAULT_NOW
) -> tuple[int, dict[str, Any]]:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    scn.write(root)
    return run_ws(root, tmp_path / f"{name}-report.json", now)


def blocking_codes(report: dict[str, Any]) -> set[str]:
    return {r["code"] for r in report["results"] if r["merge_blocking"]}


def blocking_checks(report: dict[str, Any]) -> set[str]:
    return {r["check_id"] for r in report["results"] if r["merge_blocking"]}


def all_codes(report: dict[str, Any]) -> set[str]:
    return {r["code"] for r in report["results"]}


def results_for(report: dict[str, Any], check_id: str) -> list[dict[str, Any]]:
    return [r for r in report["results"] if r["check_id"] == check_id]

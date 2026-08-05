"""Deterministic machine-readable report + human summary (contract-matrix §20)."""

from __future__ import annotations

import json
from typing import Any

from .checks import CHECKS
from .core import REPORT_SCHEMA_VERSION, REQUIRED_CHECK, TOOL_VERSION, Result, Severity


def build_report(
    results: list[Result],
    *,
    build_id: str | None,
    excluded_count: int,
    status_override: str | None = None,
) -> dict[str, Any]:
    ordered = sorted(results, key=lambda r: r.sort_key())
    errors = sum(1 for r in ordered if r.merge_blocking)
    warnings = sum(1 for r in ordered if r.severity is Severity.WARNING)
    failed_ids = {r.check_id for r in ordered if r.merge_blocking}
    failed_checks = len(failed_ids)
    passed_checks = len(CHECKS) - failed_checks
    status = status_override or ("fail" if errors else "pass")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "required_check": REQUIRED_CHECK,
        "build_id": build_id,
        "status": status,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "excluded": excluded_count,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
        },
        "results": [r.to_dict() for r in ordered],
    }


def serialize(report: dict[str, Any]) -> str:
    """Byte-stable JSON: sorted keys, 2-space indent, LF, single trailing newline."""
    return json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def human_summary(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        f"asset-production-gate: {report['status'].upper()}",
        f"  build_id: {report['build_id']}",
        f"  errors={s['errors']} warnings={s['warnings']} excluded={s['excluded']} "
        f"checks_passed={s['passed_checks']}/{s['passed_checks'] + s['failed_checks']}",
    ]
    for r in report["results"]:
        if r["merge_blocking"] or r["severity"] == "warning":
            mark = "E" if r["merge_blocking"] else "W"
            where = r["asset_id"] or r["artifact_path"] or "-"
            lines.append(f"  [{mark}] {r['check_id']} {r['code']} ({where}): {r['message']}")
    return "\n".join(lines)

"""`asset-production-gate` CLI — offline production asset validator (ASSET-OPS-004).

Exit codes (contract-matrix §19):
    0  all merge-blocking checks pass (warnings / DEPRECATED excludes allowed)
    1  >=1 merge-blocking policy/asset violation
    2  bad CLI usage / config / input path inaccessible
    3  validator internal error / report-generation failure
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from .checks import CheckContext, parse_iso, run_all
from .core import InputError
from .model import load_workspace
from .report import build_report, human_summary, serialize

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INPUT = 2
EXIT_INTERNAL = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asset-production-gate",
        description="Offline production asset validator (ASSET-OPS-004, checks C01-C26).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="validate a workspace and emit a report")
    v.add_argument(
        "--workspace",
        required=True,
        type=Path,
        help="workspace root (assets/metadata, assets/generated, ...)",
    )
    v.add_argument(
        "--report",
        type=Path,
        default=None,
        help="write the JSON report to this path (also printed to stdout)",
    )
    v.add_argument(
        "--now",
        default=None,
        help="ISO-8601 reference time for exception expiry (default: current UTC)",
    )
    v.add_argument("--quiet", action="store_true", help="suppress the human summary on stderr")
    return parser


def _resolve_now(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(UTC)
    parsed = parse_iso(raw)
    if parsed is None:
        raise InputError(f"--now is not a valid ISO-8601 timestamp: {raw!r}")
    return parsed


def _count_excluded(ctx: CheckContext) -> int:
    return sum(1 for r in ctx.ws.records if r.data.get("approval_state") == "DEPRECATED")


def run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse already printed usage
        return EXIT_INPUT if exc.code not in (0, None) else EXIT_PASS

    try:
        now = _resolve_now(args.now)
        ws = load_workspace(args.workspace)
        ctx = CheckContext.build(ws, now)
        results = run_all(ctx)
        build_id = None
        if ws.build_metadata is not None:
            bid = ws.build_metadata.get("build_id")
            build_id = bid if isinstance(bid, str) else None
        report = build_report(results, build_id=build_id, excluded_count=_count_excluded(ctx))
    except InputError as exc:
        _emit_error_report(args, str(exc), "input")
        return EXIT_INPUT
    except Exception as exc:  # noqa: BLE001 - top-level guard maps to exit 3
        _emit_error_report(args, f"{type(exc).__name__}: {exc}", "error")
        return EXIT_INTERNAL

    text = serialize(report)
    if args.report is not None:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write report to {args.report}: {exc}", file=sys.stderr)
            return EXIT_INTERNAL
    sys.stdout.write(text)
    if not args.quiet:
        print(human_summary(report), file=sys.stderr)
    return EXIT_FAIL if report["status"] == "fail" else EXIT_PASS


def _emit_error_report(args: argparse.Namespace, message: str, kind: str) -> None:
    stub: dict[str, object] = {
        "schema_version": "1.0.0",
        "tool_version": "0.1.0",
        "required_check": "asset-production-gate",
        "build_id": None,
        "status": "error",
        "summary": {
            "errors": 0,
            "warnings": 0,
            "excluded": 0,
            "passed_checks": 0,
            "failed_checks": 0,
        },
        "results": [],
        "error": {"kind": kind, "message": message},
    }
    text = serialize(stub)
    report_path = getattr(args, "report", None)
    if report_path is not None:
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(text, encoding="utf-8")
        except OSError:
            pass
    sys.stdout.write(text)
    print(f"error ({kind}): {message}", file=sys.stderr)


def main() -> None:
    raise SystemExit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()

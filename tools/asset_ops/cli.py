"""`asset-production-gate` CLI — production asset validator + manifest generator.

Subcommands:
  validate           run C01-C26 over a workspace and emit a report (ASSET-OPS-004)
  generate           assemble the Runtime Manifest + reports from metadata (P3A)
  verify-generated   regenerate, diff against committed artifacts, run the P2 gate

Exit codes:
  validate           0 pass · 1 merge-blocking violation · 2 input · 3 internal
  generate           0 success · 1 metadata/policy violation · 2 input · 3 internal
  verify-generated   0 identical+gate-pass · 1 drift or gate-fail · 2 input · 3 internal
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import generator
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
        description="Production asset validator (C01-C26) + deterministic manifest generator.",
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

    g = sub.add_parser("generate", help="assemble the runtime manifest + reports from metadata")
    g.add_argument("--workspace", required=True, type=Path, help="workspace root")
    g.add_argument("--quiet", action="store_true", help="suppress the summary on stderr")

    vg = sub.add_parser(
        "verify-generated", help="regenerate, diff committed artifacts, and run the P2 gate"
    )
    vg.add_argument("--workspace", required=True, type=Path, help="workspace root")
    vg.add_argument("--now", default=None, help="ISO-8601 reference time (default: current UTC)")
    vg.add_argument("--quiet", action="store_true", help="suppress the summary on stderr")
    return parser


def _resolve_now(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(UTC)
    parsed = parse_iso(raw)
    if parsed is None:
        raise InputError(f"--now is not a valid ISO-8601 timestamp: {raw!r}")
    return parsed


# ---- validate --------------------------------------------------------------


def _count_excluded(ctx: CheckContext) -> int:
    return sum(1 for r in ctx.ws.records if r.data.get("approval_state") == "DEPRECATED")


def _validate_report(root: Path, now: datetime) -> dict[str, Any]:
    ws = load_workspace(root)
    ctx = CheckContext.build(ws, now)
    results = run_all(ctx)
    build_id = None
    if ws.build_metadata is not None:
        bid = ws.build_metadata.get("build_id")
        build_id = bid if isinstance(bid, str) else None
    return build_report(results, build_id=build_id, excluded_count=_count_excluded(ctx))


def _run_validate(args: argparse.Namespace) -> int:
    try:
        report = _validate_report(args.workspace, _resolve_now(args.now))
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


# ---- generate --------------------------------------------------------------


def _run_generate(args: argparse.Namespace) -> int:
    try:
        outputs = generator.generate(args.workspace)
        generator._write_all(args.workspace, outputs)
    except InputError as exc:
        print(f"error (input): {exc}", file=sys.stderr)
        return EXIT_INPUT
    except Exception as exc:  # noqa: BLE001
        print(f"error (internal): {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_INTERNAL
    sys.stdout.write(serialize(outputs.validation_summary))
    if not args.quiet:
        s = outputs.validation_summary
        print(
            f"generate: included={s['included']} excluded={s['excluded']} "
            f"hard_errors={s['hard_errors']} build_id={s['build_id']}",
            file=sys.stderr,
        )
        for msg in outputs.hard_errors:
            print(f"  [E] {msg}", file=sys.stderr)
    return EXIT_FAIL if outputs.hard_errors else EXIT_PASS


# ---- verify-generated ------------------------------------------------------


def _run_verify_generated(args: argparse.Namespace) -> int:
    root: Path = args.workspace
    try:
        outputs = generator.generate(root)
        # Byte-stability: regenerating must be identical.
        again = generator.generate(root)
        if outputs.manifest_bytes() != again.manifest_bytes():
            print("error: generation is not byte-stable", file=sys.stderr)
            return EXIT_FAIL
        drift = _detect_drift(root, outputs)
        report = _validate_report(root, _resolve_now(args.now))
    except InputError as exc:
        print(f"error (input): {exc}", file=sys.stderr)
        return EXIT_INPUT
    except Exception as exc:  # noqa: BLE001
        print(f"error (internal): {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_INTERNAL

    gate_failed = report["status"] == "fail"
    if not args.quiet:
        for d in drift:
            print(f"  [DRIFT] {d}", file=sys.stderr)
        print(
            f"verify-generated: drift={len(drift)} gate={'fail' if gate_failed else 'pass'} "
            f"hard_errors={len(outputs.hard_errors)}",
            file=sys.stderr,
        )
    return EXIT_FAIL if (drift or gate_failed or outputs.hard_errors) else EXIT_PASS


def _detect_drift(root: Path, outputs: generator.GeneratedOutputs) -> list[str]:
    """Return the list of committed artifacts that differ from a fresh generation."""
    expected = {
        generator.MANIFEST_REL: outputs.manifest_bytes(),
        generator.BUILD_META_REL: generator._dumps(outputs.build_metadata),
        generator.ROLLBACK_REL: generator._dumps(outputs.rollback_index),
    }
    drift: list[str] = []
    for rel, want in expected.items():
        path = root / rel
        if not path.is_file():
            drift.append(f"{rel}: missing (not committed)")
        elif path.read_bytes() != want:
            drift.append(f"{rel}: differs from regeneration (hand-edited or stale)")
    return drift


# ---- dispatch --------------------------------------------------------------


def run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse already printed usage
        return EXIT_INPUT if exc.code not in (0, None) else EXIT_PASS
    if args.command == "generate":
        return _run_generate(args)
    if args.command == "verify-generated":
        return _run_verify_generated(args)
    return _run_validate(args)


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

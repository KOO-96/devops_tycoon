"""Input model + workspace loader for the production asset validator.

The validator consumes a *workspace* directory in the conventional layout from
`production-asset-metadata-policy.md §2`:

    <ws>/assets/metadata/**/*.json        production metadata (governance source)
    <ws>/assets/source/...                committed source binaries (image/atlas)
    <ws>/assets/generated/manifests/manifest.json
    <ws>/assets/generated/build-metadata.json
    <ws>/assets/releases/rollback-index.json
    <ws>/assets/approvals/exceptions/*.json
    <ws>/runtime-refs.json                asset ids the runtime references (optional)
    <ws>/bundle-config.json               bundle graph + transfer sizes (optional)

All source/artifact paths inside metadata are resolved relative to the workspace root.
Nothing here validates policy — loading is lenient; C01 (schema) reports malformed records.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .core import InputError


def _read_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - exercised via CLI input-error path
        raise InputError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON in {path}: {exc}") from exc


@dataclass(frozen=True)
class RawRecord:
    """A metadata record plus its on-disk provenance (never leaked to the report)."""

    data: dict[str, Any]
    rel_path: str


@dataclass
class Workspace:
    root: Path
    records: list[RawRecord] = field(default_factory=list)
    manifest: dict[str, Any] | None = None
    manifest_path: str | None = None
    build_metadata: dict[str, Any] | None = None
    rollback_index: dict[str, Any] | None = None
    exceptions: list[dict[str, Any]] = field(default_factory=list)
    runtime_refs: list[str] | None = None
    bundle_config: dict[str, Any] | None = None


def _load_dir_records(base: Path) -> list[RawRecord]:
    out: list[RawRecord] = []
    if not base.is_dir():
        return out
    for path in sorted(base.rglob("*.json")):
        data = _read_json(path)
        if not isinstance(data, dict):
            raise InputError(f"metadata record is not a JSON object: {path}")
        out.append(RawRecord(data=data, rel_path=path.relative_to(base.parent.parent).as_posix()))
    return out


def _load_exceptions(base: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not base.is_dir():
        return out
    for path in sorted(base.rglob("*.json")):
        data = _read_json(path)
        if not isinstance(data, dict):
            raise InputError(f"exception record is not a JSON object: {path}")
        out.append(data)
    return out


def _maybe_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = _read_json(path)
    if not isinstance(data, dict):
        raise InputError(f"expected a JSON object: {path}")
    return data


def load_workspace(root: Path) -> Workspace:
    if not root.is_dir():
        raise InputError(f"workspace is not a directory: {root}")

    metadata_dir = root / "assets" / "metadata"
    manifest_path = root / "assets" / "generated" / "manifests" / "manifest.json"
    build_meta_path = root / "assets" / "generated" / "build-metadata.json"
    rollback_path = root / "assets" / "releases" / "rollback-index.json"
    exceptions_dir = root / "assets" / "approvals" / "exceptions"
    runtime_refs_path = root / "runtime-refs.json"
    bundle_cfg_path = root / "bundle-config.json"

    manifest = _maybe_json_dict(manifest_path)
    runtime_refs: list[str] | None = None
    if runtime_refs_path.is_file():
        raw = _read_json(runtime_refs_path)
        if isinstance(raw, dict) and isinstance(raw.get("asset_ids"), list):
            runtime_refs = [str(x) for x in raw["asset_ids"]]
        elif isinstance(raw, list):
            runtime_refs = [str(x) for x in raw]
        else:
            raise InputError(f"runtime-refs.json must be a list or {{asset_ids: [...]}}: {root}")

    return Workspace(
        root=root,
        records=_load_dir_records(metadata_dir),
        manifest=manifest,
        manifest_path=manifest_path.relative_to(root).as_posix() if manifest is not None else None,
        build_metadata=_maybe_json_dict(build_meta_path),
        rollback_index=_maybe_json_dict(rollback_path),
        exceptions=_load_exceptions(exceptions_dir),
        runtime_refs=runtime_refs,
        bundle_config=_maybe_json_dict(bundle_cfg_path),
    )


def resolve_artifact(ws: Workspace, rel: str) -> Path:
    """Resolve a metadata source/artifact path relative to the workspace root."""
    return ws.root / rel

"""Deterministic Metadata -> Runtime Manifest generator (Asset Production Enablement P3A).

A **Python build-time tool**. It imports the shared primitives from `canonical.py`
DIRECTLY — it does NOT re-implement the inclusion predicate, the metadata->entry
mapping, canonical serialization, or `build_id`. The frontend consumes only the
generated Runtime Manifest JSON; it never re-derives any of this.

Outputs (see `generate`):
  Runtime Manifest      assets/generated/manifests/manifest.json    (committed)
  Mapping Report        assets/generated/reports/mapping-report.json (CI artifact)
  Exclusion Report      assets/generated/reports/exclusion-report.json (CI artifact)
  Validation Summary    assets/generated/reports/validation-summary.json (CI artifact)
  Build Metadata        assets/generated/build-metadata.json        (release artifact)
  Rollback Index        assets/releases/rollback-index.json         (release artifact)

The generator does NOT re-run C01-C26 — that is the P2 validator's job
(`asset-production-gate`). `verify-generated` regenerates and diffs, then runs the P2
validator so a committed artifact that would fail the gate also fails verification.

Only `source_type == image` is runtime-ready in P3A. Atlas metadata is parsed but never
emitted as a runtime-ready production entry (ATLAS_LOADER_CASE_B / BLOCKED_BY_P3B).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import canonical
from .core import INCLUDABLE_STATE, RUNTIME_CATEGORIES, InputError
from .model import _read_json

MANIFEST_REL = "assets/generated/manifests/manifest.json"
BUILD_META_REL = "assets/generated/build-metadata.json"
MAPPING_REL = "assets/generated/reports/mapping-report.json"
EXCLUSION_REL = "assets/generated/reports/exclusion-report.json"
SUMMARY_REL = "assets/generated/reports/validation-summary.json"
ROLLBACK_REL = "assets/releases/rollback-index.json"
CONFIG_REL = "assets/generator-config.json"

# Atlas is a valid production source_type but NOT runtime-ready in P3A.
RUNTIME_READY_SOURCE_TYPES: frozenset[str] = frozenset({"image"})
# Generator exclusion reason for an approved-but-not-runtime-ready atlas asset.
ATLAS_BLOCKED_CODE = "ASSET_ATLAS_BLOCKED_BY_P3B"

# Persisted, source-controlled generated baselines (verify-generated diffs these vs the
# workspace). The reports below are ephemeral CI artifacts (regenerated every run) —
# verified by A/B byte-stability + schema, NOT by repository drift.
PERSISTED_BASELINES: tuple[str, ...] = (MANIFEST_REL, BUILD_META_REL, ROLLBACK_REL)
CI_ONLY_REPORTS: tuple[str, ...] = (MAPPING_REL, EXCLUSION_REL, SUMMARY_REL)


@dataclass
class GeneratedOutputs:
    manifest: dict[str, Any]
    build_metadata: dict[str, Any]
    mapping_report: dict[str, Any]
    exclusion_report: dict[str, Any]
    validation_summary: dict[str, Any]
    rollback_index: dict[str, Any]
    hard_errors: list[str] = field(default_factory=list)

    def manifest_bytes(self) -> bytes:
        return canonical.canonical_manifest_bytes(self.manifest)

    def all_artifact_bytes(self) -> dict[str, bytes]:
        """Every generated artifact serialized — for A/B determinism comparison."""
        return {
            MANIFEST_REL: self.manifest_bytes(),
            BUILD_META_REL: _dumps(self.build_metadata),
            MAPPING_REL: _dumps(self.mapping_report),
            EXCLUSION_REL: _dumps(self.exclusion_report),
            SUMMARY_REL: _dumps(self.validation_summary),
            ROLLBACK_REL: _dumps(self.rollback_index),
        }

    def persisted_bytes(self) -> dict[str, bytes]:
        return {rel: self.all_artifact_bytes()[rel] for rel in PERSISTED_BASELINES}


def _dumps(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _load_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_REL
    if not path.is_file():
        raise InputError(f"generator config missing: {CONFIG_REL}")
    data = _read_json(path)
    if not isinstance(data, dict):
        raise InputError(f"generator config is not a JSON object: {CONFIG_REL}")
    for key in (
        "manifest_version",
        "schema_version",
        "generator_version",
        "generator_config_version",
    ):
        if not isinstance(data.get(key), str) or not data[key]:
            raise InputError(f"generator config missing string field: {key}")
    return data


def _load_metadata(root: Path) -> list[dict[str, Any]]:
    base = root / "assets" / "metadata"
    out: list[dict[str, Any]] = []
    if base.is_dir():
        for path in sorted(base.rglob("*.json")):
            data = _read_json(path)
            if not isinstance(data, dict):
                raise InputError(f"metadata record is not a JSON object: {path}")
            out.append(data)
    return out


def _classify_exclusion(data: dict[str, Any]) -> tuple[str, bool]:
    """Coarse exclusion reason + merge-blocking flag. NOT a re-implementation of the
    inclusion predicate (that stays `canonical.is_production_includable`) and NOT the
    C01-C26 codes (P2 owns those)."""
    state = data.get("approval_state")
    if state == "REVOKED":
        return "REVOKED", True
    if state == "DEPRECATED":
        return "DEPRECATED", False
    approved = data.get("production_approved")
    if (state == INCLUDABLE_STATE) != (approved is True):
        return "APPROVAL_STATE_MISMATCH", True
    if state != INCLUDABLE_STATE:
        return "NOT_PRODUCTION_APPROVED", True
    lt = data.get("license_type")
    if not isinstance(lt, str) or lt == "unknown":
        return "LICENSE_INVALID", True
    if data.get("category") not in RUNTIME_CATEGORIES:
        return "INVALID_CATEGORY", True
    return "APPROVAL_INCOMPLETE", True


def _sorted_category_fallbacks(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in sorted(raw.items())}


def _exclusion_reason_for(data: dict[str, Any], included_ids: set[str]) -> tuple[str, bool] | None:
    """Reason + blocking for a record; None when it enters the manifest.

    An includable-but-not-runtime-ready asset (atlas) is blocked (BLOCKED_BY_P3B); all
    other non-included records are classified by `_classify_exclusion`.
    """
    aid = str(data.get("asset_id"))
    if aid in included_ids:
        if data.get("source_type") in RUNTIME_READY_SOURCE_TYPES:
            return None
        return ATLAS_BLOCKED_CODE, True
    return _classify_exclusion(data)


def _mapping_reason(data: dict[str, Any], included_ids: set[str]) -> str | None:
    classified = _exclusion_reason_for(data, included_ids)
    return None if classified is None else classified[0]


def build_outputs(records: list[dict[str, Any]], config: dict[str, Any]) -> GeneratedOutputs:
    schema_version = str(config["schema_version"])
    generator_version = str(config["generator_version"])
    generator_config_version = str(config["generator_config_version"])
    manifest_version = str(config["manifest_version"])
    category_fallbacks = _sorted_category_fallbacks(config.get("category_fallbacks"))

    included = canonical.canonical_included_metadata(records)  # THE shared predicate
    included_ids = {str(d.get("asset_id")) for d in included}
    hard_errors: list[str] = []

    # runtime-ready gate: only `image` becomes a runtime entry in P3A. A non-runtime-ready
    # includable asset (atlas) is recorded in the exclusion loop below (BLOCKED_BY_P3B).
    entries: list[dict[str, Any]] = [
        canonical.metadata_to_entry(d)
        for d in included
        if d.get("source_type") in RUNTIME_READY_SOURCE_TYPES
    ]

    # Fallback targets referenced by runtime (entry + category) — used for exclusion severity.
    referenced: set[str] = set()
    for e in entries:
        fb = e.get("fallbackAssetId")
        if isinstance(fb, str):
            referenced.add(fb)
    for target in category_fallbacks.values():
        referenced.add(target)

    # Exclusions — every non-manifest record is recorded (no silent exclusion).
    exclusions: list[dict[str, Any]] = []
    for d in records:
        classified = _exclusion_reason_for(d, included_ids)
        if classified is None:
            continue  # in the manifest
        aid = str(d.get("asset_id"))
        reason, blocking = classified
        referenced_by_runtime = aid in referenced
        if referenced_by_runtime:
            blocking = True  # an excluded-but-needed fallback target is never silent
        exclusions.append(
            {
                "asset_id": aid,
                "asset_version": str(d.get("asset_version")),
                "approval_state": d.get("approval_state"),
                "exclusion_reason_code": reason,
                "source_metadata_path": None,
                "referenced_by_runtime": referenced_by_runtime,
                "merge_blocking": blocking,
                "message": f"{aid} excluded: {reason}"
                + (" (referenced by runtime fallback)" if referenced_by_runtime else ""),
            }
        )
        if reason == "REVOKED":
            hard_errors.append(f"{aid}: REVOKED asset present in generation input")
        elif reason == ATLAS_BLOCKED_CODE:
            hard_errors.append(f"{aid}: atlas source not runtime-ready in P3A (BLOCKED_BY_P3B)")
        elif blocking:
            hard_errors.append(f"{aid}: non-includable asset ({reason})")

    # categoryFallbacks target sanity (generator-side; P2 C09 is the enforced gate)
    for cat, target in category_fallbacks.items():
        if cat not in RUNTIME_CATEGORIES:
            hard_errors.append(f"categoryFallbacks['{cat}']: not a runtime AssetCategory")
        if target not in included_ids:
            hard_errors.append(f"categoryFallbacks['{cat}'] -> '{target}': not in included set")

    manifest = {
        "manifestVersion": manifest_version,
        "assets": sorted(entries, key=lambda e: (str(e["assetId"]), str(e["assetVersion"]))),
        "categoryFallbacks": category_fallbacks,
    }
    build_id = canonical.compute_build_id(
        [d for d in included if d.get("source_type") in RUNTIME_READY_SOURCE_TYPES],
        schema_version=schema_version,
        generator_version=generator_version,
        generator_config_version=generator_config_version,
    )
    build_metadata = {
        "schema_version": schema_version,
        "generator_version": generator_version,
        "generator_config_version": generator_config_version,
        "build_id": build_id,
    }
    mapping_report = {
        "entries": sorted(
            (
                {
                    "asset_id": str(d.get("asset_id")),
                    "asset_version": str(d.get("asset_version")),
                    "included": str(d.get("asset_id")) in included_ids
                    and d.get("source_type") in RUNTIME_READY_SOURCE_TYPES,
                    "runtime_manifest_index": _entry_index(manifest, d),
                    "runtime_source": canonical.metadata_to_entry(d).get("source"),
                    "runtime_checksum": canonical.metadata_to_entry(d).get("checksum"),
                    "exclusion_reason_code": _mapping_reason(d, included_ids),
                }
                for d in records
            ),
            key=lambda r: (r["asset_id"], r["asset_version"]),
        )
    }
    exclusion_report = {
        "exclusions": sorted(exclusions, key=lambda r: (r["asset_id"], r["asset_version"]))
    }
    rollback_index = {
        "candidates": [
            {
                "manifest_version": manifest_version,
                "eligible": True,
                "assets": [
                    {
                        "asset_id": str(d.get("asset_id")),
                        "asset_version": str(d.get("asset_version")),
                    }
                    for d in included
                    if d.get("source_type") in RUNTIME_READY_SOURCE_TYPES
                ],
            }
        ]
    }
    validation_summary = {
        "generated_total": len(records),
        "included": len(manifest["assets"]),
        "excluded": len(exclusions),
        "hard_errors": len(hard_errors),
        "hard_error_messages": sorted(set(hard_errors)),
        "build_id": build_id,
        "artifacts": sorted(
            [MANIFEST_REL, BUILD_META_REL, MAPPING_REL, EXCLUSION_REL, SUMMARY_REL, ROLLBACK_REL]
        ),
    }
    return GeneratedOutputs(
        manifest=manifest,
        build_metadata=build_metadata,
        mapping_report=mapping_report,
        exclusion_report=exclusion_report,
        validation_summary=validation_summary,
        rollback_index=rollback_index,
        hard_errors=sorted(set(hard_errors)),
    )


def _entry_index(manifest: dict[str, Any], data: dict[str, Any]) -> int | None:
    key = (str(data.get("asset_id")), str(data.get("asset_version")))
    for i, e in enumerate(manifest["assets"]):
        if (str(e["assetId"]), str(e["assetVersion"])) == key:
            return i
    return None


def _iter_strings(obj: Any) -> Any:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_strings(v)


def report_schema_problems(outputs: GeneratedOutputs) -> list[str]:
    """Required-field + no-absolute-path checks for the CI-only reports."""
    problems: list[str] = []
    m = outputs.mapping_report.get("entries")
    if not isinstance(m, list):
        problems.append("mapping-report: 'entries' missing or not a list")
    else:
        for e in m:
            for f in (
                "asset_id",
                "asset_version",
                "included",
                "runtime_manifest_index",
                "runtime_source",
                "runtime_checksum",
                "exclusion_reason_code",
            ):
                if f not in e:
                    problems.append(f"mapping-report entry missing '{f}'")
    x = outputs.exclusion_report.get("exclusions")
    if not isinstance(x, list):
        problems.append("exclusion-report: 'exclusions' missing or not a list")
    else:
        for e in x:
            for f in (
                "asset_id",
                "asset_version",
                "approval_state",
                "exclusion_reason_code",
                "referenced_by_runtime",
                "merge_blocking",
                "message",
            ):
                if f not in e:
                    problems.append(f"exclusion-report entry missing '{f}'")
    for f in ("generated_total", "included", "excluded", "hard_errors", "build_id"):
        if f not in outputs.validation_summary:
            problems.append(f"validation-summary missing '{f}'")
    for name, report in (
        ("mapping", outputs.mapping_report),
        ("exclusion", outputs.exclusion_report),
        ("validation-summary", outputs.validation_summary),
    ):
        if any(s.startswith("/") for s in _iter_strings(report)):
            problems.append(f"{name}-report: contains an absolute host path")
    return problems


def _write_all(root: Path, outputs: GeneratedOutputs) -> None:
    for rel, data in outputs.all_artifact_bytes().items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def generate(root: Path) -> GeneratedOutputs:
    """Assemble outputs from workspace metadata + config. Raises InputError on bad input."""
    if not root.is_dir():
        raise InputError(f"workspace is not a directory: {root}")
    config = _load_config(root)
    records = _load_metadata(root)
    return build_outputs(records, config)

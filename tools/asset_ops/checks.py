"""C01–C26 check registry for the ASSET-OPS-004 production asset validator.

Each check implements one row of `asset-ops-004-contract-matrix.md §27`. Checks are
pure over a `CheckContext` and return `Result`s. Rights/approval/integrity codes are
merge-blocking and never exceptionable; only C15/C16/C17/C18/C26 consult a DevCTO
exception record.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import canonical
from .core import (
    APPROVAL_STATES,
    CRITICAL_GPU_BYTES,
    CRITICAL_TRANSFER_BYTES,
    EXCEPTIONABLE_CHECKS,
    FRAME_NAME_RE,
    INCLUDABLE_STATE,
    MAX_FALLBACK_HOPS,
    PROD_LICENSE_TYPES,
    RESIDENT_GPU_BYTES,
    RUNTIME_CATEGORIES,
    STALE_RETENTION_MAX,
    TEXTURE_HARD_MAX,
    TEXTURE_RECOMMENDED,
    Result,
    Severity,
    err,
    gpu_bytes,
    is_valid_checksum,
    normalize_checksum,
    png_dimensions,
    sha256_hex,
    warn,
)
from .model import RawRecord, Workspace, resolve_artifact

CATEGORY_REQUIRES_ANCHOR = frozenset({"building", "tile", "ui", "character"})
CATEGORY_REQUIRES_FOOTPRINT = frozenset({"building"})


def parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass
class CheckContext:
    ws: Workspace
    now: datetime
    by_id: dict[str, list[RawRecord]] = field(default_factory=dict)
    included: list[RawRecord] = field(default_factory=list)
    _dims: dict[str, tuple[int, int] | None] = field(default_factory=dict)
    _bytes: dict[str, bytes | None] = field(default_factory=dict)

    @classmethod
    def build(cls, ws: Workspace, now: datetime) -> CheckContext:
        by_id: dict[str, list[RawRecord]] = defaultdict(list)
        included: list[RawRecord] = []
        for rec in ws.records:
            aid = rec.data.get("asset_id")
            if isinstance(aid, str):
                by_id[aid].append(rec)
            # Centralized inclusion predicate — no standalone rule duplicated here.
            if canonical.is_production_includable(rec.data):
                included.append(rec)
        included.sort(key=lambda r: (str(r.data.get("asset_id")), str(r.data.get("asset_version"))))
        return cls(ws=ws, now=now, by_id=dict(by_id), included=included)

    def read_bytes(self, rel: str) -> bytes | None:
        if rel not in self._bytes:
            path = resolve_artifact(self.ws, rel)
            try:
                self._bytes[rel] = path.read_bytes()
            except OSError:
                self._bytes[rel] = None
        return self._bytes[rel]

    def dimensions(self, rel: str) -> tuple[int, int] | None:
        if rel not in self._dims:
            data = self.read_bytes(rel)
            self._dims[rel] = png_dimensions(data) if data is not None else None
        return self._dims[rel]

    def waiver_for(self, asset_id: str | None, version: str | None, check_id: str) -> str | None:
        """Return a valid DevCTO exception id waiving `check_id` for this asset, else None."""
        if check_id not in EXCEPTIONABLE_CHECKS:
            return None
        for exc in self.ws.exceptions:
            if exc.get("check_id") != check_id:
                continue
            if exc.get("asset_id") != asset_id or exc.get("asset_version") != version:
                continue
            if exc.get("status") != "active":
                continue
            approver = exc.get("approved_by")
            if not (isinstance(approver, str) and approver.strip().lower() == "devcto"):
                continue
            expires = exc.get("expires_at") or exc.get("review_at")
            if isinstance(expires, str):
                when = parse_iso(expires)
                if when is not None and when <= self.now:
                    continue
            exc_id = exc.get("exception_id")
            return exc_id if isinstance(exc_id, str) else "unknown"
        return None


# ---- field accessors -------------------------------------------------------


def _str(d: dict[str, Any], key: str) -> str | None:
    v = d.get(key)
    return v if isinstance(v, str) else None


def _num(d: dict[str, Any], key: str) -> float | None:
    v = d.get(key)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _obj(d: dict[str, Any], key: str) -> dict[str, Any] | None:
    v = d.get(key)
    return v if isinstance(v, dict) else None


def _aid(rec: RawRecord) -> str | None:
    return _str(rec.data, "asset_id")


def _ver(rec: RawRecord) -> str | None:
    return _str(rec.data, "asset_version")


# ---- C01 schema ------------------------------------------------------------


def c01_schema(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for rec in ctx.ws.records:
        d = rec.data
        aid, ver = _aid(rec), _ver(rec)
        problems: list[str] = []
        for f in ("schema_version", "metadata_version", "asset_id", "asset_version"):
            if not _str(d, f):
                problems.append(f"missing/invalid {f}")
        category = _str(d, "category")
        if category is None:
            problems.append("missing category")
        elif category not in RUNTIME_CATEGORIES:
            problems.append(f"category '{category}' not in runtime union")
        source_type = _str(d, "source_type")
        if source_type not in {"image", "atlas"}:
            problems.append(f"source_type '{source_type}' not a production source (image|atlas)")
        elif source_type == "image":
            if not _str(d, "source_path"):
                problems.append("image requires source_path")
            if not _str(d, "checksum_sha256"):
                problems.append("image requires checksum_sha256")
        else:
            src = _obj(d, "source")
            if src is None or src.get("type") != "atlas":
                problems.append("atlas requires source.type == 'atlas'")
            else:
                for f in (
                    "atlas_json_path",
                    "atlas_image_path",
                    "atlas_json_checksum_sha256",
                    "atlas_image_checksum_sha256",
                    "frame",
                ):
                    if not (isinstance(src.get(f), str) and src[f]):
                        problems.append(f"atlas requires source.{f}")
        if category in CATEGORY_REQUIRES_ANCHOR and _obj(d, "anchor") is None:
            problems.append(f"category '{category}' requires anchor")
        if category in CATEGORY_REQUIRES_FOOTPRINT and _obj(d, "footprint") is None:
            problems.append(f"category '{category}' requires footprint")
        if not isinstance(d.get("approval_state"), str):
            problems.append("missing approval_state")
        elif d["approval_state"] not in APPROVAL_STATES:
            problems.append(f"approval_state '{d['approval_state']}' invalid")
        if not isinstance(d.get("production_approved"), bool):
            problems.append("production_approved must be a boolean")
        if problems:
            out.append(
                err(
                    "C01",
                    "SCHEMA_INVALID",
                    f"{rec.rel_path}: " + "; ".join(problems),
                    asset_id=aid,
                    asset_version=ver,
                    artifact_path=rec.rel_path,
                    details={"problems": problems},
                )
            )
    return out


# ---- C02 duplicate assetId+version ----------------------------------------


def c02_dup_asset_version(ctx: CheckContext) -> list[Result]:
    seen: dict[tuple[str, str], int] = defaultdict(int)
    for rec in ctx.ws.records:
        aid, ver = _aid(rec), _ver(rec)
        if aid and ver:
            seen[(aid, ver)] += 1
    out: list[Result] = []
    for (aid, ver), count in sorted(seen.items()):
        if count > 1:
            out.append(
                err(
                    "C02",
                    "DUP_ASSET_VERSION",
                    f"{count} records share (asset_id={aid}, asset_version={ver})",
                    asset_id=aid,
                    asset_version=ver,
                    details={"count": count},
                )
            )
    return out


# ---- C03 duplicate frame (atlas) ------------------------------------------


def c03_dup_frame(ctx: CheckContext) -> list[Result]:
    """Two metadata records claiming the same (atlas identity, frame_name).

    Atlas identity is the shared atlas descriptor (atlas_json_path); this is distinct
    from C02 (which keys on asset_id+version) — several assets may pack into one atlas.
    """
    seen: dict[tuple[str, str], list[str]] = defaultdict(list)
    for rec in ctx.ws.records:
        if _str(rec.data, "source_type") != "atlas":
            continue
        src = _obj(rec.data, "source") or {}
        atlas_id = src.get("atlas_json_path")
        frame = src.get("frame")
        aid = _aid(rec)
        if isinstance(atlas_id, str) and isinstance(frame, str) and aid is not None:
            seen[(atlas_id, frame)].append(aid)
    out: list[Result] = []
    for (atlas_id, frame), owners in sorted(seen.items()):
        if len(owners) > 1:
            out.append(
                err(
                    "C03",
                    "DUP_FRAME",
                    f"frame '{frame}' in atlas '{atlas_id}' claimed by "
                    f"{len(owners)} assets: {', '.join(sorted(owners))}",
                    artifact_path=atlas_id,
                    details={"frame": frame, "assets": sorted(owners)},
                )
            )
    return out


# ---- C04 source exists -----------------------------------------------------


def c04_source_exists(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for rec in ctx.ws.records:
        st = _str(rec.data, "source_type")
        paths: list[str] = []
        if st == "image":
            p = _str(rec.data, "source_path")
            if p:
                paths.append(p)
        elif st == "atlas":
            src = _obj(rec.data, "source") or {}
            for k in ("atlas_json_path", "atlas_image_path"):
                if isinstance(src.get(k), str):
                    paths.append(src[k])
        for p in paths:
            if ctx.read_bytes(p) is None:
                out.append(
                    err(
                        "C04",
                        "SOURCE_MISSING",
                        f"source binary not found: {p}",
                        asset_id=_aid(rec),
                        asset_version=_ver(rec),
                        artifact_path=p,
                    )
                )
    return out


# ---- C05 atlas JSON <-> image ---------------------------------------------


def _load_atlas_json(ctx: CheckContext, rel: str) -> dict[str, Any] | None:
    data = ctx.read_bytes(rel)
    if data is None:
        return None
    import json

    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def c05_atlas_consistency(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for rec in ctx.ws.records:
        if _str(rec.data, "source_type") != "atlas":
            continue
        src = _obj(rec.data, "source") or {}
        aid, ver = _aid(rec), _ver(rec)
        json_path = src.get("atlas_json_path")
        image_path = src.get("atlas_image_path")
        frame_name = src.get("frame")
        if not isinstance(json_path, str) or not isinstance(image_path, str):
            continue  # C01 covers missing paths
        descriptor = _load_atlas_json(ctx, json_path)
        if descriptor is None:
            out.append(
                err(
                    "C05",
                    "ATLAS_INCONSISTENT",
                    f"atlas descriptor missing/invalid: {json_path}",
                    asset_id=aid,
                    asset_version=ver,
                    artifact_path=json_path,
                )
            )
            continue
        # image reference inside the descriptor must match metadata atlas_image_path
        ref = (
            descriptor.get("image") or descriptor.get("meta", {}).get("image")
            if isinstance(descriptor.get("meta"), dict)
            else descriptor.get("image")
        )
        img_basename = image_path.rsplit("/", 1)[-1]
        if isinstance(ref, str) and ref.rsplit("/", 1)[-1] != img_basename:
            out.append(
                err(
                    "C05",
                    "ASSET_ATLAS_IMAGE_REFERENCE_MISMATCH",
                    f"descriptor image '{ref}' != metadata atlas_image_path '{image_path}'",
                    asset_id=aid,
                    asset_version=ver,
                    artifact_path=json_path,
                    details={"descriptor_image": ref, "metadata_image": image_path},
                )
            )
        dims = ctx.dimensions(image_path)
        frames = descriptor.get("frames")
        seen_frames: set[str] = set()
        if isinstance(frames, dict):
            items = [(str(k), v) for k, v in frames.items()]
        elif isinstance(frames, list):
            items = [(str(fr.get("name")), fr) for fr in frames if isinstance(fr, dict)]
        else:
            items = []
        for name, fr in items:
            if name in seen_frames:
                out.append(
                    err(
                        "C05",
                        "ATLAS_INCONSISTENT",
                        f"duplicate frame '{name}' in {json_path}",
                        asset_id=aid,
                        asset_version=ver,
                        artifact_path=json_path,
                    )
                )
            seen_frames.add(name)
            rect = fr.get("frame") if isinstance(fr, dict) else None
            rect = rect if isinstance(rect, dict) else fr
            if dims and isinstance(rect, dict):
                x, y = _num(rect, "x") or 0.0, _num(rect, "y") or 0.0
                w, h = _num(rect, "w") or 0.0, _num(rect, "h") or 0.0
                if x < 0 or y < 0 or x + w > dims[0] or y + h > dims[1]:
                    out.append(
                        err(
                            "C05",
                            "ATLAS_INCONSISTENT",
                            f"frame '{name}' {int(x)},{int(y)},{int(w)},{int(h)} out of "
                            f"image bounds {dims[0]}x{dims[1]}",
                            asset_id=aid,
                            asset_version=ver,
                            artifact_path=json_path,
                            details={"frame": name, "image_size": list(dims)},
                        )
                    )
        if isinstance(frame_name, str) and frame_name not in seen_frames:
            out.append(
                err(
                    "C05",
                    "ATLAS_INCONSISTENT",
                    f"metadata frame '{frame_name}' not present in descriptor {json_path}",
                    asset_id=aid,
                    asset_version=ver,
                    artifact_path=json_path,
                    details={"frame": frame_name},
                )
            )
    return out


# ---- C06 frame-name convention --------------------------------------------


def c06_frame_name(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for rec in ctx.ws.records:
        if _str(rec.data, "source_type") != "atlas":
            continue
        src = _obj(rec.data, "source") or {}
        frame = src.get("frame")
        if isinstance(frame, str) and not FRAME_NAME_RE.match(frame):
            out.append(
                err(
                    "C06",
                    "FRAME_NAME_INVALID",
                    f"frame name '{frame}' violates convention [a-z0-9]([-_][a-z0-9])*",
                    asset_id=_aid(rec),
                    asset_version=_ver(rec),
                    details={"frame": frame},
                )
            )
    return out


# ---- C07 anchor range ------------------------------------------------------


def c07_anchor_range(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for rec in ctx.ws.records:
        anchor = _obj(rec.data, "anchor")
        if anchor is None:
            continue
        for axis in ("x", "y"):
            v = _num(anchor, axis)
            if v is None or v < 0.0 or v > 1.0:
                out.append(
                    err(
                        "C07",
                        "ANCHOR_RANGE",
                        f"anchor.{axis}={anchor.get(axis)} not in [0,1]",
                        asset_id=_aid(rec),
                        asset_version=_ver(rec),
                    )
                )
    return out


# ---- C08 footprint range ---------------------------------------------------


def c08_footprint_range(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for rec in ctx.ws.records:
        fp = _obj(rec.data, "footprint")
        if fp is None:
            continue
        for dim in ("width", "height"):
            v = fp.get(dim)
            if not isinstance(v, int) or isinstance(v, bool) or v < 1 or v > 4:
                out.append(
                    err(
                        "C08",
                        "FOOTPRINT_RANGE",
                        f"footprint.{dim}={v} not an integer in 1..4",
                        asset_id=_aid(rec),
                        asset_version=_ver(rec),
                    )
                )
    return out


# ---- manifest categoryFallbacks helpers -----------------------------------
# The runtime manifest carries `categoryFallbacks: Partial<Record<AssetCategory,
# assetId>>` (metadata-policy §10c). C09/C10/C11 validate the *combined* fallback
# graph over three edge kinds, resolved in this order:
#   1. Entry:     assetId -> entry.fallbackAssetId          (when present)
#   2. Category:  assetId -> categoryFallbacks[category]     (when no entry fb)
#   3. Universal: terminal (no outgoing edge)
# A "hop" is one traversal of an Entry-or-Category edge; the Universal terminal is
# NOT an edge and is never counted as a cycle. Max chain depth is MAX_FALLBACK_HOPS.


def _manifest_asset_index(ctx: CheckContext) -> dict[str, dict[str, Any]]:
    manifest = ctx.ws.manifest or {}
    assets = manifest.get("assets")
    out: dict[str, dict[str, Any]] = {}
    if isinstance(assets, list):
        for e in assets:
            if isinstance(e, dict) and isinstance(e.get("assetId"), str):
                out[e["assetId"]] = e
    return out


def _category_fallbacks(ctx: CheckContext) -> Any:
    return (ctx.ws.manifest or {}).get("categoryFallbacks")


def _combined_fallback_edges(ctx: CheckContext) -> dict[str, str | None]:
    """asset_id -> resolved fallback (entry fb, else category fb, else None terminal)."""
    assets = _manifest_asset_index(ctx)
    catfb = _category_fallbacks(ctx)
    catfb = catfb if isinstance(catfb, dict) else {}
    edges: dict[str, str | None] = {}
    for aid, entry in assets.items():
        fb = entry.get("fallbackAssetId")
        if isinstance(fb, str) and fb:
            edges[aid] = fb
            continue
        cat = entry.get("category")
        cfb = catfb.get(cat) if isinstance(cat, str) else None
        edges[aid] = cfb if isinstance(cfb, str) and cfb else None
    return edges


def _chain_hops(edges: dict[str, str | None], start: str) -> int:
    hops = 0
    node: str | None = start
    visited: set[str] = {start}
    while isinstance(node, str) and node in edges:
        nxt = edges.get(node)
        if not isinstance(nxt, str):
            break  # terminal
        hops += 1
        if nxt in visited:
            break  # cycle — reported by C10, not depth
        visited.add(nxt)
        node = nxt
    return hops


# ---- C09 fallback exists ---------------------------------------------------


def c09_fallback_exists(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    ids = set(ctx.by_id)
    for rec in ctx.ws.records:
        fb = _str(rec.data, "fallback_asset_id")
        if fb and fb not in ids:
            out.append(
                err(
                    "C09",
                    "FALLBACK_MISSING",
                    f"fallback_asset_id '{fb}' does not resolve",
                    asset_id=_aid(rec),
                    asset_version=_ver(rec),
                    details={"fallback": fb},
                )
            )
    out.extend(_c09_category_fallbacks(ctx))
    return out


def _c09_category_fallbacks(ctx: CheckContext) -> list[Result]:
    """Manifest categoryFallbacks: key validity + target existence/inclusion."""
    if ctx.ws.manifest is None:
        return []
    catfb = _category_fallbacks(ctx)
    if catfb is None:
        return []  # optional field absent
    if not isinstance(catfb, dict):
        return [
            err(
                "C09",
                "ASSET_CATEGORY_FALLBACK_INVALID_KEY",
                "manifest categoryFallbacks must be an object",
                artifact_path="categoryFallbacks",
            )
        ]
    assets = _manifest_asset_index(ctx)
    included_ids = {r.data.get("asset_id") for r in ctx.included}
    includable_by_id: dict[str, bool] = {}
    state_by_id: dict[str, str | None] = {}
    for rec in ctx.ws.records:
        aid = _aid(rec)
        if aid is None:
            continue
        includable_by_id[aid] = includable_by_id.get(
            aid, False
        ) or canonical.is_production_includable(rec.data)
        state_by_id.setdefault(aid, _str(rec.data, "approval_state"))
    out: list[Result] = []
    for key in sorted(catfb):
        loc = f"categoryFallbacks.{key}"
        target = catfb[key]
        if key not in RUNTIME_CATEGORIES:
            out.append(
                err(
                    "C09",
                    "ASSET_CATEGORY_FALLBACK_INVALID_KEY",
                    f"categoryFallbacks key '{key}' is not a runtime AssetCategory",
                    artifact_path=loc,
                    details={"key": key},
                )
            )
            continue
        if not isinstance(target, str) or not target:
            out.append(
                err(
                    "C09",
                    "ASSET_CATEGORY_FALLBACK_TARGET_MISSING",
                    f"categoryFallbacks['{key}'] target is not a valid assetId",
                    artifact_path=loc,
                    details={"key": key},
                )
            )
            continue
        if target in includable_by_id and not includable_by_id[target]:
            out.append(
                err(
                    "C09",
                    "ASSET_CATEGORY_FALLBACK_TARGET_EXCLUDED",
                    f"categoryFallbacks['{key}'] -> '{target}' is an excluded asset "
                    f"(state {state_by_id.get(target)})",
                    artifact_path=loc,
                    details={"key": key, "target": target, "state": state_by_id.get(target)},
                )
            )
            continue
        if target not in assets:
            out.append(
                err(
                    "C09",
                    "ASSET_CATEGORY_FALLBACK_TARGET_MISSING",
                    f"categoryFallbacks['{key}'] -> '{target}' is not in manifest assets",
                    artifact_path=loc,
                    details={"key": key, "target": target},
                )
            )
            continue
        if target not in included_ids:
            out.append(
                err(
                    "C09",
                    "ASSET_CATEGORY_FALLBACK_TARGET_EXCLUDED",
                    f"categoryFallbacks['{key}'] -> '{target}' is not in the approved included set",
                    artifact_path=loc,
                    details={"key": key, "target": target},
                )
            )
    return out


# ---- C10 fallback cycle / C11 fallback depth ------------------------------


def _fallback_edges(ctx: CheckContext) -> dict[str, str]:
    edges: dict[str, str] = {}
    for rec in ctx.ws.records:
        aid, fb = _aid(rec), _str(rec.data, "fallback_asset_id")
        if aid and fb:
            edges[aid] = fb
    return edges


def c10_fallback_cycle(ctx: CheckContext) -> list[Result]:
    edges = _fallback_edges(ctx)
    out: list[Result] = []
    for start in sorted(edges):
        seen: list[str] = []
        node: str | None = start
        while node is not None and node in edges:
            if node in seen:
                cycle = seen[seen.index(node) :] + [node]
                out.append(
                    err(
                        "C10",
                        "FALLBACK_CYCLE",
                        "fallback cycle: " + " -> ".join(cycle),
                        asset_id=start,
                        details={"cycle": cycle},
                    )
                )
                break
            seen.append(node)
            node = edges.get(node)
    out.extend(_c10_category_cycle(ctx))
    return out


def _c10_category_cycle(ctx: CheckContext) -> list[Result]:
    if ctx.ws.manifest is None:
        return []
    edges = _combined_fallback_edges(ctx)
    out: list[Result] = []
    reported: set[tuple[str, ...]] = set()
    for start in sorted(edges):
        seen: list[str] = []
        node: str | None = start
        while isinstance(node, str) and node in edges:
            if node in seen:
                cycle = seen[seen.index(node) :] + [node]
                key = tuple(sorted(set(cycle)))
                if key not in reported:
                    reported.add(key)
                    out.append(
                        err(
                            "C10",
                            "ASSET_CATEGORY_FALLBACK_CYCLE",
                            "combined fallback cycle: " + " -> ".join(cycle),
                            artifact_path="categoryFallbacks",
                            details={"cycle": cycle},
                        )
                    )
                break
            seen.append(node)
            node = edges.get(node)
    return out


def c11_fallback_depth(ctx: CheckContext) -> list[Result]:
    edges = _fallback_edges(ctx)
    out: list[Result] = []
    for start in sorted(edges):
        hops = 0
        node: str | None = start
        visited: set[str] = set()
        while node is not None and node in edges:
            if node in visited:
                break  # cycle handled by C10
            visited.add(node)
            node = edges.get(node)
            hops += 1
            if hops > MAX_FALLBACK_HOPS:
                out.append(
                    err(
                        "C11",
                        "FALLBACK_DEPTH",
                        f"fallback chain from '{start}' exceeds {MAX_FALLBACK_HOPS} hops",
                        asset_id=start,
                        details={"hops": hops},
                    )
                )
                break
    out.extend(_c11_category_depth(ctx))
    return out


def _c11_category_depth(ctx: CheckContext) -> list[Result]:
    if ctx.ws.manifest is None:
        return []
    edges = _combined_fallback_edges(ctx)
    out: list[Result] = []
    for start in sorted(edges):
        hops = _chain_hops(edges, start)
        if hops > MAX_FALLBACK_HOPS:
            out.append(
                err(
                    "C11",
                    "ASSET_CATEGORY_FALLBACK_DEPTH_EXCEEDED",
                    f"combined fallback chain from '{start}' exceeds {MAX_FALLBACK_HOPS} hops",
                    asset_id=start,
                    artifact_path="categoryFallbacks",
                    details={"hops": hops},
                )
            )
    return out


# ---- C12 checksum integrity -----------------------------------------------


def c12_checksum(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for rec in ctx.ws.records:
        st = _str(rec.data, "source_type")
        aid, ver = _aid(rec), _ver(rec)
        if st == "image":
            declared = _str(rec.data, "checksum_sha256")
            path = _str(rec.data, "source_path")
            if declared is None or path is None:
                continue
            _verify(ctx, out, "C12", "ASSET_CHECKSUM_IMAGE_MISMATCH", aid, ver, path, declared)
        elif st == "atlas":
            src = _obj(rec.data, "source") or {}
            jp, ip = src.get("atlas_json_path"), src.get("atlas_image_path")
            jc, ic = src.get("atlas_json_checksum_sha256"), src.get("atlas_image_checksum_sha256")
            if isinstance(jp, str) and isinstance(jc, str):
                _verify(ctx, out, "C12", "ASSET_CHECKSUM_ATLAS_JSON_MISMATCH", aid, ver, jp, jc)
            if isinstance(ip, str) and isinstance(ic, str):
                _verify(ctx, out, "C12", "ASSET_CHECKSUM_ATLAS_IMAGE_MISMATCH", aid, ver, ip, ic)
    return out


def _verify(
    ctx: CheckContext,
    out: list[Result],
    check: str,
    code: str,
    aid: str | None,
    ver: str | None,
    path: str,
    declared: str,
) -> None:
    if not is_valid_checksum(declared):
        out.append(
            err(
                check,
                code,
                f"checksum for {path} is not a 64-hex sha256",
                asset_id=aid,
                asset_version=ver,
                artifact_path=path,
            )
        )
        return
    data = ctx.read_bytes(path)
    if data is None:
        return  # C04 reports the missing binary
    actual = sha256_hex(data)
    if actual != normalize_checksum(declared):
        out.append(
            err(
                check,
                code,
                f"checksum mismatch for {path}",
                asset_id=aid,
                asset_version=ver,
                artifact_path=path,
                details={"declared": normalize_checksum(declared), "actual": actual},
            )
        )


# ---- C13 license -----------------------------------------------------------


def c13_license(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for rec in ctx.ws.records:
        lt = _str(rec.data, "license_type")
        aid, ver = _aid(rec), _ver(rec)
        if lt is None or lt == "unknown" or lt not in PROD_LICENSE_TYPES:
            out.append(
                err(
                    "C13",
                    "LICENSE_INVALID",
                    f"license_type '{lt}' is not a valid production license",
                    asset_id=aid,
                    asset_version=ver,
                    details={"license_type": lt},
                )
            )
            continue
        if not _str(rec.data, "license_reference"):
            out.append(
                err(
                    "C13",
                    "LICENSE_INVALID",
                    f"license_type '{lt}' requires license_reference evidence",
                    asset_id=aid,
                    asset_version=ver,
                )
            )
        if lt == "generative_output":
            prov = _obj(rec.data, "source_provenance") or {}
            if not _str(prov, "prompt_hash") or prov.get("human_reviewed") is not True:
                out.append(
                    err(
                        "C13",
                        "LICENSE_INVALID",
                        "generative_output requires prompt_hash + human_reviewed=true",
                        asset_id=aid,
                        asset_version=ver,
                    )
                )
    return out


# ---- C14 production approval -----------------------------------------------


def c14_approval(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for rec in ctx.ws.records:
        d = rec.data
        aid, ver = _aid(rec), _ver(rec)
        state = _str(d, "approval_state")
        approved = d.get("production_approved")
        # boolean must match state (subordinate invariant)
        if (state == INCLUDABLE_STATE) != (approved is True):
            out.append(
                err(
                    "C14",
                    "APPROVAL_INVALID",
                    f"production_approved={approved} inconsistent with approval_state={state}",
                    asset_id=aid,
                    asset_version=ver,
                )
            )
        if state != INCLUDABLE_STATE:
            continue
        approval = _obj(d, "approval") or {}
        missing = [
            f
            for f in (
                "reviewed_asset_version",
                "approved_by",
                "approved_at",
                "rights_review_reference",
                "technical_review_reference",
            )
            if not _str(approval, f)
        ]
        if missing:
            out.append(
                err(
                    "C14",
                    "APPROVAL_INVALID",
                    f"APPROVED_FOR_PRODUCTION missing approval fields: {', '.join(missing)}",
                    asset_id=aid,
                    asset_version=ver,
                    details={"missing": missing},
                )
            )
        elif approval.get("reviewed_asset_version") != ver:
            out.append(
                err(
                    "C14",
                    "APPROVAL_INVALID",
                    f"approval bound to version '{approval.get('reviewed_asset_version')}' "
                    f"but asset_version is '{ver}'",
                    asset_id=aid,
                    asset_version=ver,
                )
            )
    return out


# ---- C15 texture dimension -------------------------------------------------


def c15_texture_dimension(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for rec in ctx.ws.records:
        if _str(rec.data, "source_type") != "image":
            continue
        path = _str(rec.data, "source_path")
        if not path:
            continue
        dims = ctx.dimensions(path)
        if dims is None:
            continue
        w, h = dims
        aid, ver = _aid(rec), _ver(rec)
        if max(w, h) > TEXTURE_HARD_MAX:
            wid = ctx.waiver_for(aid, ver, "C15")
            res = err(
                "C15",
                "TEXTURE_DIMENSION",
                f"texture {w}x{h} exceeds hard-max {TEXTURE_HARD_MAX}",
                asset_id=aid,
                asset_version=ver,
                artifact_path=path,
            )
            out.append(_maybe_waive(res, wid))
        elif max(w, h) > TEXTURE_RECOMMENDED:
            out.append(
                warn(
                    "C15",
                    "TEXTURE_DIMENSION",
                    f"texture {w}x{h} exceeds recommended {TEXTURE_RECOMMENDED} (<= hard-max)",
                    asset_id=aid,
                    asset_version=ver,
                    artifact_path=path,
                )
            )
    return out


# ---- C16 atlas dimension ---------------------------------------------------


def _is_pot(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def c16_atlas_dimension(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for rec in ctx.ws.records:
        if _str(rec.data, "source_type") != "atlas":
            continue
        src = _obj(rec.data, "source") or {}
        path = src.get("atlas_image_path")
        if not isinstance(path, str):
            continue
        dims = ctx.dimensions(path)
        if dims is None:
            continue
        w, h = dims
        aid, ver = _aid(rec), _ver(rec)
        if max(w, h) > TEXTURE_HARD_MAX:
            wid = ctx.waiver_for(aid, ver, "C16")
            out.append(
                _maybe_waive(
                    err(
                        "C16",
                        "ATLAS_DIMENSION",
                        f"atlas {w}x{h} exceeds hard-max {TEXTURE_HARD_MAX}",
                        asset_id=aid,
                        asset_version=ver,
                        artifact_path=path,
                    ),
                    wid,
                )
            )
        elif not (_is_pot(w) and _is_pot(h)):
            out.append(
                warn(
                    "C16",
                    "ATLAS_DIMENSION",
                    f"atlas {w}x{h} SHOULD be power-of-two",
                    asset_id=aid,
                    asset_version=ver,
                    artifact_path=path,
                )
            )
    return out


# ---- C17 bundle transfer size ----------------------------------------------


def _critical_bundles(ctx: CheckContext) -> set[str]:
    cfg = ctx.ws.bundle_config or {}
    crit = cfg.get("critical_bundles")
    return {str(b) for b in crit} if isinstance(crit, list) else set()


def c17_bundle_size(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    critical = _critical_bundles(ctx)
    if not critical:
        return out
    sizes: dict[str, int] = defaultdict(int)
    owners: dict[str, str] = {}
    for rec in ctx.included:
        bundle = _str(rec.data, "bundle")
        if bundle is None:
            continue
        owners[str(_aid(rec))] = bundle
        for p in _artifact_paths(rec):
            data = ctx.read_bytes(p)
            if data is not None:
                sizes[bundle] += len(data)
    for bundle in sorted(critical):
        total = sizes.get(bundle, 0)
        if total > CRITICAL_TRANSFER_BYTES:
            wid = _waiver_any(ctx, bundle, "C17")
            out.append(
                _maybe_waive(
                    err(
                        "C17",
                        "BUNDLE_SIZE",
                        f"critical bundle '{bundle}' transfer {total} B exceeds "
                        f"{CRITICAL_TRANSFER_BYTES} B budget",
                        artifact_path=bundle,
                        details={"bytes": total},
                    ),
                    wid,
                )
            )
    return out


def _artifact_paths(rec: RawRecord) -> list[str]:
    st = _str(rec.data, "source_type")
    if st == "image":
        p = _str(rec.data, "source_path")
        return [p] if p else []
    if st == "atlas":
        src = _obj(rec.data, "source") or {}
        keys = ("atlas_json_path", "atlas_image_path")
        return [src[k] for k in keys if isinstance(src.get(k), str)]
    return []


def _waiver_any(ctx: CheckContext, key: str, check: str) -> str | None:
    for exc in ctx.ws.exceptions:
        if (
            exc.get("check_id") == check
            and exc.get("asset_id") == key
            and exc.get("status") == "active"
            and isinstance(exc.get("approved_by"), str)
            and exc["approved_by"].strip().lower() == "devcto"
        ):
            eid = exc.get("exception_id")
            return eid if isinstance(eid, str) else "unknown"
    return None


# ---- C18 GPU memory --------------------------------------------------------


def c18_gpu_memory(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    critical = _critical_bundles(ctx)
    resident_total = 0
    critical_total = 0
    for rec in ctx.included:
        path = _image_for_memory(rec)
        if path is None:
            continue
        dims = ctx.dimensions(path)
        if dims is None:
            continue
        mem = gpu_bytes(dims[0], dims[1], mipmap=rec.data.get("mipmap") is True)
        resident_total += mem
        if _str(rec.data, "bundle") in critical:
            critical_total += mem
    if critical and critical_total > CRITICAL_GPU_BYTES:
        out.append(
            err(
                "C18",
                "GPU_MEMORY",
                f"critical GPU memory {critical_total} B exceeds {CRITICAL_GPU_BYTES} B",
                details={"bytes": critical_total},
            )
        )
    if resident_total > RESIDENT_GPU_BYTES:
        out.append(
            err(
                "C18",
                "GPU_MEMORY",
                f"resident GPU memory {resident_total} B exceeds {RESIDENT_GPU_BYTES} B",
                details={"bytes": resident_total},
            )
        )
    return out


def _image_for_memory(rec: RawRecord) -> str | None:
    st = _str(rec.data, "source_type")
    if st == "image":
        return _str(rec.data, "source_path")
    if st == "atlas":
        src = _obj(rec.data, "source") or {}
        return src.get("atlas_image_path") if isinstance(src.get("atlas_image_path"), str) else None
    return None


# ---- C19 unused manifest entry / C20 unmanifested runtime asset ------------


def _manifest_ids(ctx: CheckContext) -> set[str]:
    manifest = ctx.ws.manifest or {}
    assets = manifest.get("assets")
    ids: set[str] = set()
    if isinstance(assets, list):
        for e in assets:
            if isinstance(e, dict) and isinstance(e.get("assetId"), str):
                ids.add(e["assetId"])
    return ids


def c19_unused_entry(ctx: CheckContext) -> list[Result]:
    if ctx.ws.manifest is None or ctx.ws.runtime_refs is None:
        return []
    refs = set(ctx.ws.runtime_refs)
    out: list[Result] = []
    for aid in sorted(_manifest_ids(ctx)):
        if aid not in refs:
            out.append(
                warn(
                    "C19",
                    "UNUSED_ENTRY",
                    f"manifest asset '{aid}' is not referenced by any runtime kind",
                    asset_id=aid,
                )
            )
    return out


def c20_unmanifested(ctx: CheckContext) -> list[Result]:
    if ctx.ws.runtime_refs is None:
        return []
    manifest_ids = _manifest_ids(ctx)
    out: list[Result] = []
    for aid in sorted(set(ctx.ws.runtime_refs)):
        if aid not in manifest_ids:
            out.append(
                err(
                    "C20",
                    "UNMANIFESTED_ASSET",
                    f"runtime-needed asset '{aid}' is absent from the manifest",
                    asset_id=aid,
                )
            )
    return out


# ---- C21 metadata <-> manifest mapping ------------------------------------


def c21_mapping(ctx: CheckContext) -> list[Result]:
    if ctx.ws.manifest is None:
        return []
    entries: dict[str, dict[str, Any]] = {}
    assets = ctx.ws.manifest.get("assets")
    if isinstance(assets, list):
        for e in assets:
            if (
                isinstance(e, dict)
                and isinstance(e.get("assetId"), str)
                and isinstance(e.get("assetVersion"), str)
            ):
                entries[f"{e['assetId']}@{e['assetVersion']}"] = e
    out: list[Result] = []
    for rec in ctx.included:
        aid, ver = _aid(rec), _ver(rec)
        key = f"{aid}@{ver}"
        expected = canonical.metadata_to_entry(rec.data)
        actual = entries.get(key)
        if actual is None:
            out.append(
                err(
                    "C21",
                    "MAPPING_MISMATCH",
                    f"approved asset {key} has no manifest entry",
                    asset_id=aid,
                    asset_version=ver,
                )
            )
            continue
        leaked = sorted(set(actual) & canonical.GOVERNANCE_EXCLUDED_MANIFEST_FIELDS)
        if leaked:
            out.append(
                err(
                    "C21",
                    "MAPPING_MISMATCH",
                    f"manifest entry {key} leaks governance fields: {', '.join(leaked)}",
                    asset_id=aid,
                    asset_version=ver,
                    details={"leaked": leaked},
                )
            )
        diffs = _entry_diffs(expected, actual)
        if diffs:
            out.append(
                err(
                    "C21",
                    "MAPPING_MISMATCH",
                    f"manifest entry {key} differs from mapping: {', '.join(diffs)}",
                    asset_id=aid,
                    asset_version=ver,
                    details={"diffs": diffs},
                )
            )
    return out


def _entry_diffs(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    diffs: list[str] = []
    for k, v in expected.items():
        av = actual.get(k)
        if k == "checksum" and isinstance(av, str):
            av = normalize_checksum(av)
        if av != v:
            diffs.append(f"{k}: expected {v!r} got {av!r}")
    return diffs


# ---- C22 deterministic generation -----------------------------------------


def c22_deterministic(ctx: CheckContext) -> list[Result]:
    if ctx.ws.manifest is None or ctx.ws.manifest_path is None:
        return []
    raw = ctx.read_bytes(ctx.ws.manifest_path)
    if raw is None:
        return []
    expected = canonical.canonical_manifest_bytes(ctx.ws.manifest)
    if raw != expected:
        return [
            err(
                "C22",
                "NONDETERMINISTIC",
                "committed manifest is not in canonical byte-stable form "
                "(hand-edited or non-conforming generator)",
                artifact_path=ctx.ws.manifest_path,
            )
        ]
    return []


# ---- C23 bundle dependency cycle ------------------------------------------


def c23_bundle_cycle(ctx: CheckContext) -> list[Result]:
    cfg = ctx.ws.bundle_config or {}
    deps = cfg.get("bundle_dependencies")
    out: list[Result] = []
    graph: dict[str, list[str]] = {}
    if isinstance(deps, dict):
        for k, v in deps.items():
            if isinstance(v, list):
                graph[str(k)] = [str(x) for x in v]
    color: dict[str, int] = {}

    def visit(node: str, stack: list[str]) -> None:
        color[node] = 1
        for nxt in graph.get(node, []):
            if color.get(nxt) == 1:
                cyc = stack[stack.index(nxt) :] + [nxt] if nxt in stack else [node, nxt]
                out.append(
                    err(
                        "C23",
                        "BUNDLE_CYCLE",
                        "bundle cycle: " + " -> ".join(cyc),
                        details={"cycle": cyc},
                    )
                )
            elif color.get(nxt) is None:
                visit(nxt, stack + [nxt])
        color[node] = 2

    for node in sorted(graph):
        if color.get(node) is None:
            visit(node, [node])
    # shared asset single-owner
    owner: dict[str, str] = {}
    for rec in ctx.ws.records:
        aid, bundle = _aid(rec), _str(rec.data, "bundle")
        if aid and bundle:
            if aid in owner and owner[aid] != bundle:
                out.append(
                    err(
                        "C23",
                        "BUNDLE_CYCLE",
                        f"asset '{aid}' owned by multiple bundles: {owner[aid]}, {bundle}",
                        asset_id=aid,
                    )
                )
            owner.setdefault(aid, bundle)
    return out


# ---- C24 build-id consistency ---------------------------------------------


def c24_build_id(ctx: CheckContext) -> list[Result]:
    bm = ctx.ws.build_metadata
    if bm is None:
        if ctx.included:
            return [
                err(
                    "C24",
                    "BUILD_ID_MISMATCH",
                    "approved assets exist but no build-metadata (build_id) is present",
                )
            ]
        return []
    schema_v = _str(bm, "schema_version") or ""
    gen_v = _str(bm, "generator_version") or ""
    cfg_v = _str(bm, "generator_config_version") or ""
    expected = canonical.compute_build_id(
        [r.data for r in ctx.included],
        schema_version=schema_v,
        generator_version=gen_v,
        generator_config_version=cfg_v,
    )
    declared = _str(bm, "build_id")
    if declared != expected:
        return [
            err(
                "C24",
                "BUILD_ID_MISMATCH",
                "build_id does not match the canonical envelope of included assets",
                details={"declared": declared, "expected": expected},
            )
        ]
    return []


# ---- C25 rollback artifact -------------------------------------------------


def c25_rollback(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    state_by_id: dict[str, str] = {}
    for rec in ctx.ws.records:
        aid, st = _aid(rec), _str(rec.data, "approval_state")
        if aid and st:
            state_by_id[aid] = st
    index = ctx.ws.rollback_index
    if index is None:
        if ctx.included:
            out.append(
                err(
                    "C25",
                    "ROLLBACK_MISSING",
                    "approved assets exist but no rollback index is present",
                )
            )
        return out
    candidates = index.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        out.append(err("C25", "ROLLBACK_MISSING", "rollback index has no candidates"))
        return out
    safe_exists = False
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        label = str(cand.get("manifest_version") or cand.get("release_id") or "?")
        assets = cand.get("assets")
        revoked = []
        if isinstance(assets, list):
            for a in assets:
                if isinstance(a, dict) and state_by_id.get(str(a.get("asset_id"))) == "REVOKED":
                    revoked.append(str(a.get("asset_id")))
        eligible = cand.get("eligible") is True
        if revoked:
            out.append(
                err(
                    "C25",
                    "ASSET_ROLLBACK_REVOKED_TARGET",
                    f"rollback candidate '{label}' reactivates REVOKED asset(s): "
                    f"{', '.join(sorted(set(revoked)))}",
                    details={"candidate": label, "revoked": sorted(set(revoked))},
                )
            )
        elif eligible:
            safe_exists = True
    if not safe_exists:
        out.append(
            err(
                "C25",
                "ROLLBACK_MISSING",
                "no safe (no-REVOKED, eligible) rollback candidate exists",
            )
        )
    return out


# ---- C26 stale-version retention ------------------------------------------


def c26_stale_retention(ctx: CheckContext) -> list[Result]:
    out: list[Result] = []
    for aid in sorted(ctx.by_id):
        versions = ctx.by_id[aid]
        retained = [r for r in versions if _str(r.data, "approval_state") != "REVOKED"]
        if len(retained) > STALE_RETENTION_MAX:
            wid = _waiver_any(ctx, aid, "C26")
            out.append(
                _maybe_waive(
                    err(
                        "C26",
                        "STALE_RETENTION",
                        f"asset '{aid}' retains {len(retained)} versions (> {STALE_RETENTION_MAX})",
                        asset_id=aid,
                        details={"retained": len(retained)},
                    ),
                    wid,
                )
            )
    return out


def _maybe_waive(result: Result, exception_id: str | None) -> Result:
    """Downgrade a merge-blocking result to a non-blocking waived warning."""
    if exception_id is None:
        return result
    return Result(
        check_id=result.check_id,
        code=result.code,
        severity=Severity.WARNING,
        merge_blocking=False,
        asset_id=result.asset_id,
        asset_version=result.asset_version,
        artifact_path=result.artifact_path,
        message=result.message + " [waived by DevCTO exception]",
        exception_id=exception_id,
        details={**result.details, "waived": True},
    )


CHECKS: dict[str, Callable[[CheckContext], list[Result]]] = {
    "C01": c01_schema,
    "C02": c02_dup_asset_version,
    "C03": c03_dup_frame,
    "C04": c04_source_exists,
    "C05": c05_atlas_consistency,
    "C06": c06_frame_name,
    "C07": c07_anchor_range,
    "C08": c08_footprint_range,
    "C09": c09_fallback_exists,
    "C10": c10_fallback_cycle,
    "C11": c11_fallback_depth,
    "C12": c12_checksum,
    "C13": c13_license,
    "C14": c14_approval,
    "C15": c15_texture_dimension,
    "C16": c16_atlas_dimension,
    "C17": c17_bundle_size,
    "C18": c18_gpu_memory,
    "C19": c19_unused_entry,
    "C20": c20_unmanifested,
    "C21": c21_mapping,
    "C22": c22_deterministic,
    "C23": c23_bundle_cycle,
    "C24": c24_build_id,
    "C25": c25_rollback,
    "C26": c26_stale_retention,
}


def run_all(ctx: CheckContext) -> list[Result]:
    results: list[Result] = []
    for check_id in sorted(CHECKS):
        results.extend(CHECKS[check_id](ctx))
    return results

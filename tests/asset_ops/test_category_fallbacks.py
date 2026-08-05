"""Manifest-level categoryFallbacks validation (C09) + runtime-alignment regressions.

Runtime-aligned per the P2 corrections: the resolver
(frontend/src/game/pixi/assets/AssetManager.ts `resolveTiered`) is a FIXED, non-recursive
candidate sequence (primary -> entry -> category -> universal), so it is cycle-free and
bounded by construction. The validator therefore checks categoryFallbacks KEYS/TARGETS
(C09) only — it does NOT model a transitive combined cycle/depth graph. Manifests that
the runtime resolves safely must PASS.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from tools.asset_ops.report import human_summary
from tools.asset_ops.runtime_contract import (
    UNIVERSAL_FALLBACK_ASSET_ID,
    candidate_sequence,
    fallback_hops,
)

from tests.asset_ops._helpers import blocking_checks, blocking_codes, run_scenario, run_ws
from tests.assets.fixtures.builder import Scenario, base_scenario

BUILDING = "building-load-balancer.json"
BUILDING_ID = "building.load-balancer.primary"
UNIVERSAL = "fallback.universal.primary"
VECTORS = Path(__file__).parent / "vectors" / "fallback_candidate_sequence.json"


# ---- C09 negatives (key / target / governance) ----------------------------


def f_unknown_key(s: Scenario) -> None:
    s.category_fallbacks = {"widget": UNIVERSAL, "building": UNIVERSAL, "ui": UNIVERSAL}
    s.resync()


def f_target_missing(s: Scenario) -> None:
    s.category_fallbacks = {"building": "no.such.asset", "ui": UNIVERSAL}
    s.resync()


def f_empty_target(s: Scenario) -> None:
    s.category_fallbacks = {"building": "", "ui": UNIVERSAL}
    s.resync()


def f_target_excluded(s: Scenario) -> None:
    s.add_image_asset(
        "tile.legacy.primary", "tile", anchor={"x": 0.5, "y": 0.5}, approval_state="DEPRECATED"
    )
    s.category_fallbacks = {"tile": "tile.legacy.primary", "building": UNIVERSAL, "ui": UNIVERSAL}
    s.resync()


def f_target_revoked(s: Scenario) -> None:
    s.add_image_asset(
        "tile.revoked.primary", "tile", anchor={"x": 0.5, "y": 0.5}, approval_state="REVOKED"
    )
    s.category_fallbacks = {"tile": "tile.revoked.primary", "building": UNIVERSAL, "ui": UNIVERSAL}
    s.resync()


# (name, mutator, expected_code)  — all under C09
C09_NEGATIVES: list[tuple[str, Callable[[Scenario], None], str]] = [
    ("unknown_key", f_unknown_key, "ASSET_CATEGORY_FALLBACK_INVALID_KEY"),
    ("target_missing", f_target_missing, "ASSET_CATEGORY_FALLBACK_TARGET_MISSING"),
    ("empty_target", f_empty_target, "ASSET_CATEGORY_FALLBACK_TARGET_MISSING"),
    ("target_excluded", f_target_excluded, "ASSET_CATEGORY_FALLBACK_TARGET_EXCLUDED"),
    ("target_revoked", f_target_revoked, "ASSET_CATEGORY_FALLBACK_TARGET_EXCLUDED"),
]


def test_c09_category_fallbacks_negatives(tmp_path: Path) -> None:
    failures: list[str] = []
    for name, mutate, code in C09_NEGATIVES:
        scn = base_scenario()
        mutate(scn)
        rc, report = run_scenario(scn, tmp_path, name=f"catfb-{name}")
        if rc != 1:
            failures.append(f"{name}: expected exit 1, got {rc}")
        if code not in blocking_codes(report):
            failures.append(f"{name}: expected {code}, got {sorted(blocking_codes(report))}")
        if blocking_checks(report) != {"C09"}:
            failures.append(f"{name}: expected ONLY C09, got {sorted(blocking_checks(report))}")
    assert not failures, "\n".join(failures)


def test_c09_non_object_category_fallbacks(tmp_path: Path) -> None:
    s = base_scenario()
    s.resync()
    assert s.manifest is not None
    s.manifest["categoryFallbacks"] = ["not", "an", "object"]  # tampered manifest
    rc, report = run_scenario(s, tmp_path, name="catfb-nonobject")
    assert rc == 1
    assert "ASSET_CATEGORY_FALLBACK_INVALID_KEY" in blocking_codes(report)


def test_target_excluded_details_distinguish_state(tmp_path: Path) -> None:
    s = base_scenario()
    f_target_revoked(s)
    _, report = run_scenario(s, tmp_path, name="catfb-revoked-state")
    excluded = [
        r for r in report["results"] if r["code"] == "ASSET_CATEGORY_FALLBACK_TARGET_EXCLUDED"
    ]
    assert excluded and excluded[0]["details"].get("state") == "REVOKED"


# ---- Runtime-valid regressions (previously false-positive negatives) -------


def r_combined_depth_4(s: Scenario) -> None:
    del s.records[BUILDING]["fallback_asset_id"]
    s.add_image_asset("tile.x1.primary", "tile", anchor={"x": 0.5, "y": 0.5})
    s.add_image_asset("ui.x2.primary", "ui", anchor={"x": 0.5, "y": 0.5})
    s.add_image_asset("character.x3.primary", "character", anchor={"x": 0.5, "y": 0.5})
    s.add_image_asset("effect.x4.primary", "effect")
    s.category_fallbacks = {
        "building": "tile.x1.primary",
        "tile": "ui.x2.primary",
        "ui": "character.x3.primary",
        "character": "effect.x4.primary",
    }
    s.resync()


def r_entry_to_category_cycle(s: Scenario) -> None:
    s.records[BUILDING]["fallback_asset_id"] = "tile.other.primary"
    s.add_image_asset("tile.other.primary", "tile", anchor={"x": 0.5, "y": 0.5})
    s.category_fallbacks = {"tile": BUILDING_ID, "building": UNIVERSAL, "ui": UNIVERSAL}
    s.resync()


def r_category_to_entry_cycle(s: Scenario) -> None:
    del s.records[BUILDING]["fallback_asset_id"]
    s.add_image_asset(
        "tile.other.primary", "tile", anchor={"x": 0.5, "y": 0.5}, fallback=BUILDING_ID
    )
    s.category_fallbacks = {"building": "tile.other.primary", "ui": UNIVERSAL}
    s.resync()


def r_category_target_has_own_fallback(s: Scenario) -> None:
    # Category target itself has a fallbackAssetId — the runtime never recurses into it.
    del s.records[BUILDING]["fallback_asset_id"]
    s.add_image_asset("tile.cat.primary", "tile", anchor={"x": 0.5, "y": 0.5}, fallback=UNIVERSAL)
    s.category_fallbacks = {"building": "tile.cat.primary", "ui": UNIVERSAL}
    s.resync()


RUNTIME_VALID: list[tuple[str, Callable[[Scenario], None]]] = [
    ("combined_depth_4", r_combined_depth_4),
    ("entry_to_category_cycle", r_entry_to_category_cycle),
    ("category_to_entry_cycle", r_category_to_entry_cycle),
    ("category_target_has_own_fallback", r_category_target_has_own_fallback),
]


def test_runtime_valid_category_fallbacks_pass(tmp_path: Path) -> None:
    """Manifests the linear resolver handles safely must NOT be rejected."""
    failures: list[str] = []
    for name, mutate in RUNTIME_VALID:
        scn = base_scenario()
        mutate(scn)
        rc, report = run_scenario(scn, tmp_path, name=f"rt-{name}")
        catfb = {c for c in blocking_codes(report) if c.startswith("ASSET_CATEGORY_FALLBACK")}
        if rc != 0:
            failures.append(
                f"{name}: expected exit 0, got {rc} (blocking {sorted(blocking_codes(report))})"
            )
        if catfb:
            failures.append(f"{name}: unexpected categoryFallbacks failures {sorted(catfb)}")
    assert not failures, "\n".join(failures)


def test_valid_category_fallbacks_passes(tmp_path: Path) -> None:
    s = base_scenario()
    s.category_fallbacks = {"building": UNIVERSAL, "ui": UNIVERSAL, "tile": UNIVERSAL}
    s.resync()
    rc, report = run_scenario(s, tmp_path, name="catfb-valid")
    assert rc == 0
    assert report["status"] == "pass"


# ---- Determinism ----------------------------------------------------------


def test_category_fallbacks_report_is_order_independent(tmp_path: Path) -> None:
    s1 = base_scenario()
    s1.category_fallbacks = {"building": UNIVERSAL, "ui": UNIVERSAL, "tile": UNIVERSAL}
    s1.resync()
    s2 = base_scenario()
    s2.category_fallbacks = {"tile": UNIVERSAL, "ui": UNIVERSAL, "building": UNIVERSAL}
    s2.resync()
    root1, root2 = tmp_path / "o1", tmp_path / "o2"
    root1.mkdir(parents=True, exist_ok=True)
    root2.mkdir(parents=True, exist_ok=True)
    s1.write(root1)
    s2.write(root2)
    _, rep1 = run_ws(root1, tmp_path / "o1.json")
    _, rep2 = run_ws(root2, tmp_path / "o2.json")
    assert (tmp_path / "o1.json").read_bytes() == (tmp_path / "o2.json").read_bytes()
    assert human_summary(rep1) == human_summary(rep2)
    assert str(tmp_path) not in (tmp_path / "o1.json").read_text(encoding="utf-8")


# ---- Runtime candidate-sequence conformance (shared vectors) --------------


def test_candidate_sequence_matches_runtime_vectors() -> None:
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    universal = data["universalFallbackAssetId"]
    max_depth = data["maxFallbackDepth"]
    for case in data["cases"]:
        seq = candidate_sequence(
            case["assets"], case["categoryFallbacks"], case["request"], universal_id=universal
        )
        assert seq == case["expectedCandidates"], case["name"]
        assert seq[0] == case["request"], case["name"]  # primary first
        assert seq[-1] == universal, case["name"]  # universal terminal last
        assert fallback_hops(seq) <= max_depth, case["name"]  # fixed bound


def test_candidate_sequence_never_recurses_into_target_fallback() -> None:
    # A category target with its own fallbackAssetId: its fallback must NOT appear.
    assets = {
        "building.a": {"category": "building"},
        "tile.c": {"category": "tile", "fallbackAssetId": "tile.deep"},
    }
    seq = candidate_sequence(assets, {"building": "tile.c"}, "building.a")
    assert "tile.deep" not in seq
    assert seq == ["building.a", "tile.c", UNIVERSAL_FALLBACK_ASSET_ID]

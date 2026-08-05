"""Manifest-level categoryFallbacks validation (C09/C10/C11 combined fallback graph).

Independent negative fixtures per the P2 corrections §7, plus a valid case and a
determinism check. Each negative fails on exactly the target check/code, exit 1.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tools.asset_ops.report import human_summary

from tests.asset_ops._helpers import (
    blocking_checks,
    blocking_codes,
    run_scenario,
    run_ws,
)
from tests.assets.fixtures.builder import Scenario, base_scenario

BUILDING = "building-load-balancer.json"
BUILDING_ID = "building.load-balancer.primary"
UNIVERSAL = "fallback.universal.primary"


def f_unknown_key(s: Scenario) -> None:
    s.category_fallbacks = {"widget": UNIVERSAL, "building": UNIVERSAL, "ui": UNIVERSAL}
    s.resync()


def f_target_missing(s: Scenario) -> None:
    s.category_fallbacks = {"building": "no.such.asset", "ui": UNIVERSAL}
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


def f_entry_to_category_cycle(s: Scenario) -> None:
    s.records[BUILDING]["fallback_asset_id"] = "tile.other.primary"  # entry edge lb -> other
    s.add_image_asset("tile.other.primary", "tile", anchor={"x": 0.5, "y": 0.5})  # no entry fb
    s.category_fallbacks = {"tile": BUILDING_ID, "building": UNIVERSAL, "ui": UNIVERSAL}
    s.resync()


def f_category_to_entry_cycle(s: Scenario) -> None:
    del s.records[BUILDING]["fallback_asset_id"]  # lb has no entry fb -> uses category
    s.add_image_asset(
        "tile.other.primary", "tile", anchor={"x": 0.5, "y": 0.5}, fallback=BUILDING_ID
    )  # entry edge other -> lb
    s.category_fallbacks = {"building": "tile.other.primary", "ui": UNIVERSAL}
    s.resync()


def f_combined_depth_4(s: Scenario) -> None:
    del s.records[BUILDING]["fallback_asset_id"]  # lb resolves via category
    s.add_image_asset("tile.x1.primary", "tile", anchor={"x": 0.5, "y": 0.5})
    s.add_image_asset("ui.x2.primary", "ui", anchor={"x": 0.5, "y": 0.5})
    s.add_image_asset("character.x3.primary", "character", anchor={"x": 0.5, "y": 0.5})
    s.add_image_asset("effect.x4.primary", "effect")  # effect needs no anchor
    s.category_fallbacks = {
        "building": "tile.x1.primary",
        "tile": "ui.x2.primary",
        "ui": "character.x3.primary",
        "character": "effect.x4.primary",
    }
    s.resync()


# (name, mutator, expected_check, expected_code)
NEGATIVES: list[tuple[str, Callable[[Scenario], None], str, str]] = [
    ("unknown_key", f_unknown_key, "C09", "ASSET_CATEGORY_FALLBACK_INVALID_KEY"),
    ("target_missing", f_target_missing, "C09", "ASSET_CATEGORY_FALLBACK_TARGET_MISSING"),
    ("target_excluded", f_target_excluded, "C09", "ASSET_CATEGORY_FALLBACK_TARGET_EXCLUDED"),
    ("target_revoked", f_target_revoked, "C09", "ASSET_CATEGORY_FALLBACK_TARGET_EXCLUDED"),
    ("entry_to_category_cycle", f_entry_to_category_cycle, "C10", "ASSET_CATEGORY_FALLBACK_CYCLE"),
    ("category_to_entry_cycle", f_category_to_entry_cycle, "C10", "ASSET_CATEGORY_FALLBACK_CYCLE"),
    ("combined_depth_4", f_combined_depth_4, "C11", "ASSET_CATEGORY_FALLBACK_DEPTH_EXCEEDED"),
]


def test_category_fallbacks_negative_fixtures(tmp_path: Path) -> None:
    failures: list[str] = []
    for name, mutate, check, code in NEGATIVES:
        scn = base_scenario()
        mutate(scn)
        rc, report = run_scenario(scn, tmp_path, name=f"catfb-{name}")
        b_codes = blocking_codes(report)
        b_checks = blocking_checks(report)
        if rc != 1:
            failures.append(f"{name}: expected exit 1, got {rc}")
        if code not in b_codes:
            failures.append(f"{name}: expected {code}, got {sorted(b_codes)}")
        if b_checks != {check}:
            failures.append(f"{name}: expected ONLY {check} to block, got {sorted(b_checks)}")
    assert not failures, "\n".join(failures)


def test_valid_category_fallbacks_passes(tmp_path: Path) -> None:
    s = base_scenario()
    s.category_fallbacks = {"building": UNIVERSAL, "ui": UNIVERSAL, "tile": UNIVERSAL}
    s.resync()
    rc, report = run_scenario(s, tmp_path, name="catfb-valid")
    assert rc == 0
    assert report["status"] == "pass"
    assert not any(c.startswith("ASSET_CATEGORY_FALLBACK") for c in blocking_codes(report))


def test_category_fallbacks_report_is_order_independent(tmp_path: Path) -> None:
    # Same content, different dict insertion order -> byte-identical report + summary.
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


def test_category_fallbacks_errors_are_deterministic(tmp_path: Path) -> None:
    # Multiple violations, shuffled key order -> identical report bytes both runs.
    def make(order: list[str]) -> Scenario:
        s = base_scenario()
        s.category_fallbacks = dict.fromkeys(order, "no.such.asset")
        s.resync()
        return s

    s1 = make(["widget", "gadget", "sprocket"])
    s2 = make(["sprocket", "widget", "gadget"])
    root1, root2 = tmp_path / "d1", tmp_path / "d2"
    root1.mkdir(parents=True, exist_ok=True)
    root2.mkdir(parents=True, exist_ok=True)
    s1.write(root1)
    s2.write(root2)
    run_ws(root1, tmp_path / "d1.json")
    run_ws(root2, tmp_path / "d2.json")
    assert (tmp_path / "d1.json").read_bytes() == (tmp_path / "d2.json").read_bytes()

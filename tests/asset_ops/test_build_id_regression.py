"""build_id inclusion-set regression (P2 corrections §9), after centralizing the
inclusion predicate in canonical.py. Excluded states must not perturb build_id;
approved-set/binary changes must; a state/boolean mismatch is excluded AND fails."""

from __future__ import annotations

import copy
from pathlib import Path

from tools.asset_ops import canonical

from tests.asset_ops._helpers import blocking_codes, run_scenario
from tests.assets.fixtures.builder import _image_record, base_scenario

BUILDING_ID = "building.load-balancer.primary"


def _bid(records: list[dict[str, object]]) -> str:
    incl = canonical.canonical_included_metadata(records)
    return canonical.compute_build_id(
        incl, schema_version="1.0.0", generator_version="1", generator_config_version="1"
    )


def _base_records() -> list[dict[str, object]]:
    return [copy.deepcopy(r) for r in base_scenario().records.values()]


def _extra(asset_id: str, state: str) -> dict[str, object]:
    rec = _image_record(
        asset_id, "tile", "assets/source/fallback.png", "e" * 64, anchor={"x": 0.5, "y": 0.5}
    )
    if state != "APPROVED_FOR_PRODUCTION":
        rec["approval_state"] = state
        rec["production_approved"] = False
    return rec


def test_draft_deprecated_revoked_do_not_change_build_id() -> None:
    base = _base_records()
    b0 = _bid(base)
    for state in ("DRAFT", "DEPRECATED", "REVOKED"):
        assert _bid([*base, _extra(f"tile.x.{state.lower()}", state)]) == b0, state


def test_approved_binary_checksum_change_changes_build_id() -> None:
    base = _base_records()
    b0 = _bid(base)
    changed = copy.deepcopy(base)
    for r in changed:
        if r.get("asset_id") == BUILDING_ID:
            r["checksum_sha256"] = "f" * 64  # simulate a new approved binary
    assert _bid(changed) != b0


def test_approved_included_set_change_changes_build_id() -> None:
    base = _base_records()
    b0 = _bid(base)
    added = [*base, _extra("tile.new.primary", "APPROVED_FOR_PRODUCTION")]
    assert _bid(added) != b0


def test_state_boolean_mismatch_is_excluded_and_validator_fails(tmp_path: Path) -> None:
    s = base_scenario()
    with_building = _bid([copy.deepcopy(r) for r in s.records.values()])
    # APPROVED state but production_approved False -> inconsistent -> excluded + C14 error
    s.records["building-load-balancer.json"]["production_approved"] = False
    s.resync()
    without_building = _bid([copy.deepcopy(r) for r in s.records.values()])
    rc, report = run_scenario(s, tmp_path, name="mismatch")

    assert without_building != with_building  # the mismatch is not in the build_id set
    assert report["build_id"] == without_building
    assert rc == 1
    assert "APPROVAL_INVALID" in blocking_codes(report)

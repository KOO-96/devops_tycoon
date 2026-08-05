"""DevCTO exception waivers, never-exceptionable checks, C19 warnings, C25 REVOKED rollback."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from tools.asset_ops.core import sha256_hex

from tests.asset_ops._helpers import blocking_codes, results_for, run_scenario
from tests.assets.fixtures.builder import FUTURE, Scenario, base_scenario, make_png

BUILDING = "building-load-balancer.json"
BUILDING_ID = "building.load-balancer.primary"
BADGE = "ui-incident-badge.json"


def _oversize_building(s: Scenario) -> None:
    png = make_png(4097, 8)
    s.binaries["assets/source/load-balancer.png"] = png
    s.records[BUILDING]["checksum_sha256"] = sha256_hex(png)
    s.resync()


def _exception(
    check_id: str,
    *,
    approver: str = "DevCTO",
    status: str = "active",
    expires: str = FUTURE,
    asset_id: str = BUILDING_ID,
    version: str = "1",
) -> dict[str, Any]:
    return {
        "exception_id": f"exc-{check_id.lower()}",
        "asset_id": asset_id,
        "asset_version": version,
        "check_id": check_id,
        "requested_value": "4097px",
        "budget_impact": "negligible",
        "justification": "hero art needs 4097px width",
        "alternatives_considered": "downscale rejected by design",
        "approved_by": approver,
        "approved_at": "2026-01-01T00:00:00+00:00",
        "expires_at": expires,
        "status": status,
    }


def test_c15_waived_by_valid_devcto_exception(tmp_path: Path) -> None:
    s = base_scenario()
    _oversize_building(s)
    s.exceptions["exc-c15"] = _exception("C15")
    rc, report = run_scenario(s, tmp_path, name="c15-waived")
    assert rc == 0
    assert report["status"] == "pass"
    assert "TEXTURE_DIMENSION" not in blocking_codes(report)
    waived = [r for r in results_for(report, "C15") if r["exception_id"] == "exc-c15"]
    assert waived and waived[0]["severity"] == "warning" and not waived[0]["merge_blocking"]


def test_c15_not_waived_when_exception_expired(tmp_path: Path) -> None:
    s = base_scenario()
    _oversize_building(s)
    s.exceptions["exc-c15"] = _exception("C15", expires="2025-01-01T00:00:00+00:00")
    rc, report = run_scenario(s, tmp_path, name="c15-expired")
    assert rc == 1
    assert "TEXTURE_DIMENSION" in blocking_codes(report)


def test_c15_not_waived_when_approver_not_devcto(tmp_path: Path) -> None:
    s = base_scenario()
    _oversize_building(s)
    s.exceptions["exc-c15"] = _exception("C15", approver="ops-lead")
    rc, report = run_scenario(s, tmp_path, name="c15-wrong-approver")
    assert rc == 1
    assert "TEXTURE_DIMENSION" in blocking_codes(report)


def test_never_exceptionable_check_ignores_exception(tmp_path: Path) -> None:
    s = base_scenario()
    s.records[BUILDING]["license_type"] = "unknown"
    s.resync()
    # Even a well-formed DevCTO exception cannot waive a rights check (C13).
    s.exceptions["exc-c13"] = _exception("C13")
    rc, report = run_scenario(s, tmp_path, name="c13-noexcept")
    assert rc == 1
    assert "LICENSE_INVALID" in blocking_codes(report)


def test_c26_stale_retention_waived(tmp_path: Path) -> None:
    s = base_scenario()
    for v in ("2", "3", "4"):
        rec = copy.deepcopy(s.records[BUILDING])
        rec["asset_version"] = v
        rec["approval"]["reviewed_asset_version"] = v
        s.records[f"building-v{v}.json"] = rec
    s.resync()
    s.exceptions["exc-c26"] = _exception("C26")
    rc, report = run_scenario(s, tmp_path, name="c26-waived")
    assert rc == 0
    assert "STALE_RETENTION" not in blocking_codes(report)


def test_c19_unused_entry_is_warning_only(tmp_path: Path) -> None:
    s = base_scenario()
    s.runtime_refs = ["building.load-balancer.primary", "fallback.universal.primary"]  # drop badge
    rc, report = run_scenario(s, tmp_path, name="c19")
    assert rc == 0
    assert report["status"] == "pass"
    warns = [r for r in results_for(report, "C19") if r["code"] == "UNUSED_ENTRY"]
    assert warns and warns[0]["severity"] == "warning" and not warns[0]["merge_blocking"]


def test_c25_revoked_candidate_is_ineligible(tmp_path: Path) -> None:
    s = base_scenario()
    # Revoke the badge asset (consistent boolean) and drop it from runtime refs + manifest.
    s.records[BADGE]["approval_state"] = "REVOKED"
    s.records[BADGE]["production_approved"] = False
    s.runtime_refs = ["building.load-balancer.primary", "fallback.universal.primary"]
    s.regenerate_derived()  # manifest/build_id now exclude the revoked asset
    s.rollback_index = {
        "candidates": [
            {  # unsafe: reactivates a REVOKED asset
                "manifest_version": "0",
                "eligible": True,
                "assets": [{"asset_id": "ui.incident.badge", "asset_version": "1"}],
            },
            {  # safe fallback candidate exists
                "manifest_version": "1",
                "eligible": True,
                "assets": [
                    {"asset_id": "building.load-balancer.primary", "asset_version": "1"},
                    {"asset_id": "fallback.universal.primary", "asset_version": "1"},
                ],
            },
        ]
    }
    rc, report = run_scenario(s, tmp_path, name="c25-revoked")
    assert rc == 1
    assert "ASSET_ROLLBACK_REVOKED_TARGET" in blocking_codes(report)
    # never exceptionable — even a DevCTO exception must not clear it
    s.exceptions["exc-c25"] = _exception("C25", asset_id="ui.incident.badge")
    rc2, report2 = run_scenario(s, tmp_path, name="c25-revoked-excepted")
    assert rc2 == 1
    assert "ASSET_ROLLBACK_REVOKED_TARGET" in blocking_codes(report2)

"""SYNTHETIC do-not-merge enforcement probe (P2-OPS-FU-001).

Makes the `asset-production-gate` check FAIL (the validator correctly returns exit 1 on a
synthetic checksum-mismatch workspace) so we can prove Branch Protection blocks the merge.
No production assets/metadata. Removed in the follow-up commit to show the check go green.
"""

from __future__ import annotations

from pathlib import Path

from tests.asset_ops._helpers import blocking_codes, run_scenario
from tests.assets.fixtures.builder import base_scenario


def test_gate_enforcement_failure_probe(tmp_path: Path) -> None:
    s = base_scenario()
    s.records["building-load-balancer.json"]["checksum_sha256"] = "0" * 64  # C12 mismatch
    s.resync()
    rc, report = run_scenario(s, tmp_path, name="probe")
    # Inverted on purpose: the validator correctly exits 1, so this assertion fails the check.
    assert rc == 0, f"enforcement probe: validator exited {rc}, codes={sorted(blocking_codes(report))}"

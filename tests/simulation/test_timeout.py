from __future__ import annotations

import unittest

from simulation.engine import step

from tests.simulation._helpers import build_cluster


class TestTimeout(unittest.TestCase):
    def test_sustained_overload_causes_timeouts(self) -> None:
        state, config = build_cluster(users=5000)
        cfg = config.with_overrides({"request_timeout_ticks": 2})
        result = step(state, [], cfg, ticks=8)
        self.assertGreater(result.snapshot.traffic["timed_out"], 0)

    def test_timeout_incident_triggers(self) -> None:
        state, config = build_cluster(users=5000)
        cfg = config.with_overrides({"request_timeout_ticks": 2})
        result = step(state, [], cfg, ticks=8)
        keys = list(result.state.incidents.active.keys())
        self.assertTrue(
            any("REQUEST_TIMEOUT" in k for k in keys),
            f"expected timeout incident, got {keys}",
        )

    def test_retries_are_bounded(self) -> None:
        state, config = build_cluster(users=5000)
        cfg = config.with_overrides({"request_timeout_ticks": 2})
        result = step(state, [], cfg, ticks=30)
        ceiling = cfg.get_int("retry_ceiling")
        self.assertLessEqual(result.state.pending_retries, ceiling, "retry storm must be bounded")

    def test_no_timeout_when_capacity_sufficient(self) -> None:
        state, config = build_cluster(users=50)
        result = step(state, [], config, ticks=10)
        self.assertEqual(result.snapshot.traffic["timed_out"], 0)


if __name__ == "__main__":
    unittest.main()

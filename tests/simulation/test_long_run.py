from __future__ import annotations

import math
import unittest

from simulation.engine import step
from tests.simulation._helpers import build_cluster


class TestLongRun(unittest.TestCase):
    def test_long_run_is_stable(self) -> None:
        state, config = build_cluster(seed=11, users=1500)
        cfg = config.with_overrides({"traffic_jitter": 3})
        result = step(state, [], cfg, ticks=2000)

        self.assertEqual(result.state.clock.tick, 2000)

        # No NaN/Infinity/unexpected-negative anywhere in resource state.
        for server in result.state.app_servers.values():
            for value in (server.cpu_usage, server.mem_usage):
                self.assertFalse(math.isnan(value))
                self.assertFalse(math.isinf(value))
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)
            self.assertGreaterEqual(server.queue_length, 0)
        for db in result.state.databases.values():
            self.assertGreaterEqual(db.active_connections, 0)
            self.assertLessEqual(db.active_connections, db.max_connections)
        self.assertGreaterEqual(result.state.user_trust, 0.0)

    def test_event_log_is_bounded(self) -> None:
        state, config = build_cluster(users=1500)
        result = step(state, [], config, ticks=2000)
        self.assertLessEqual(
            len(result.state.events.items),
            result.state.events.max_size,
            "event log must be bounded (ring buffer)",
        )

    def test_pending_retries_bounded_over_long_run(self) -> None:
        state, config = build_cluster(users=8000)
        cfg = config.with_overrides({"request_timeout_ticks": 2})
        result = step(state, [], cfg, ticks=500)
        self.assertLessEqual(result.state.pending_retries, cfg.get_int("retry_ceiling"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from simulation.engine import step
from simulation.nodes.base import Health
from simulation.resources.cpu import cpu_usage
from simulation.resources.memory import memory_usage
from simulation.resources.queue import drain_queue

from tests.simulation._helpers import build_cluster


class TestResourceMath(unittest.TestCase):
    def test_cpu_scales_and_clamps(self) -> None:
        self.assertAlmostEqual(cpu_usage(10, 0.02), 0.2)
        self.assertEqual(cpu_usage(1000, 0.02), 1.0)  # clamped
        self.assertEqual(cpu_usage(0, 0.02), 0.0)

    def test_memory_includes_leak_and_queue(self) -> None:
        self.assertAlmostEqual(memory_usage(0.5, 10, 0.01), 0.6)
        self.assertEqual(memory_usage(0.99, 100, 0.1), 1.0)  # clamped

    def test_queue_drain_and_timeout(self) -> None:
        processed, remaining, timed_out = drain_queue(backlog=100, drain_rate=20, timeout_ticks=2)
        self.assertEqual(processed, 20)
        # remaining 80; capacity within timeout = 40 -> 40 time out.
        self.assertEqual(timed_out, 40)
        self.assertEqual(remaining, 40)


class TestAppServerIntegration(unittest.TestCase):
    def test_cpu_rises_under_load(self) -> None:
        state, config = build_cluster(users=3000)
        cfg = config.with_overrides({"request_cpu_cost": 0.05})
        result = step(state, [], cfg, ticks=5)
        cpus = [s.cpu_usage for s in result.state.app_servers.values()]
        self.assertTrue(any(c >= 0.9 for c in cpus), "CPU should saturate under heavy load")

    def test_queue_grows_when_overloaded(self) -> None:
        state, config = build_cluster(users=3000)
        result = step(state, [], config, ticks=10)
        queues = [s.queue_length for s in result.state.app_servers.values()]
        self.assertTrue(any(q > 0 for q in queues))

    def test_resources_drain_when_idle(self) -> None:
        state, config = build_cluster(users=3000)
        loaded = step(state, [], config, ticks=8)
        # Drop users to zero; queues should drain back toward empty.
        loaded.state.users = 0
        idle = step(loaded.state, [], config, ticks=40)
        queues = [s.queue_length for s in idle.state.app_servers.values()]
        self.assertTrue(all(q == 0 for q in queues))

    def test_memory_leak_downs_server(self) -> None:
        state, config = build_cluster(users=100, app_count=1)
        state.app_servers["app-1"].mem_leak_per_tick = 0.2
        result = step(state, [], config, ticks=10)
        self.assertEqual(result.state.app_servers["app-1"].health, Health.DOWN)


if __name__ == "__main__":
    unittest.main()

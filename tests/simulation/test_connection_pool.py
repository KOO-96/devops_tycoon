from __future__ import annotations

import unittest

from simulation.commands import CommandType
from simulation.engine import step
from simulation.resources.connection_pool import allocate_connections

from tests.simulation._helpers import build_cluster, make_command


class TestConnectionPoolMath(unittest.TestCase):
    def test_allocation_and_waiting(self) -> None:
        active, waiting = allocate_connections(demand=120, max_connections=100)
        self.assertEqual(active, 100)
        self.assertEqual(waiting, 20)

    def test_no_waiting_when_under_capacity(self) -> None:
        active, waiting = allocate_connections(demand=30, max_connections=100)
        self.assertEqual(active, 30)
        self.assertEqual(waiting, 0)


class TestConnectionPoolIntegration(unittest.TestCase):
    def test_small_pool_exhausts(self) -> None:
        state, config = build_cluster(users=4000, with_cache=False)
        small_pool = make_command("pool", CommandType.SET_DB_POOL, "db", max_connections=10)
        result = step(state, [small_pool], config, ticks=4)
        db = result.state.databases["db"]
        self.assertGreater(db.waiting_connections, 0)
        keys = list(result.state.incidents.active.keys())
        self.assertTrue(
            any("DB_CONNECTION_POOL_EXHAUSTION" in k for k in keys),
            f"expected pool exhaustion incident, got {keys}",
        )

    def test_pool_exhausted_event(self) -> None:
        state, config = build_cluster(users=4000, with_cache=False)
        small_pool = make_command("pool", CommandType.SET_DB_POOL, "db", max_connections=5)
        result = step(state, [small_pool], config, ticks=3)
        types = {e.type.value for e in result.events}
        self.assertIn("CONNECTION_POOL_EXHAUSTED", types)

    def test_large_pool_saturates_db_cpu(self) -> None:
        # P6: enlarging the pool admits more queries but pushes DB CPU up.
        state, config = build_cluster(users=6000, with_cache=False)
        big_pool = make_command("pool", CommandType.SET_DB_POOL, "db", max_connections=100)
        result = step(state, [big_pool], config, ticks=3)
        db = result.state.databases["db"]
        self.assertGreaterEqual(db.cpu_usage, 0.9)

    def test_returned_connections_recover(self) -> None:
        state, config = build_cluster(users=4000, with_cache=False)
        small = make_command("pool", CommandType.SET_DB_POOL, "db", max_connections=10)
        loaded = step(state, [small], config, ticks=4)
        loaded.state.users = 0
        # Enough idle ticks for the backlog built during overload to drain.
        recovered = step(loaded.state, [], config, ticks=120)
        self.assertEqual(recovered.state.databases["db"].active_connections, 0)


if __name__ == "__main__":
    unittest.main()

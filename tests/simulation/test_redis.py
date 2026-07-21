from __future__ import annotations

import unittest

from simulation.commands import CommandType
from simulation.engine import step
from tests.simulation._helpers import build_cluster, make_command


class TestRedis(unittest.TestCase):
    def test_cache_hit_reduces_db_load(self) -> None:
        with_cache, config = build_cluster(users=1000, with_cache=True)
        no_cache, _ = build_cluster(users=1000, with_cache=False)
        r_cache = step(with_cache, [], config, ticks=3)
        r_nocache = step(no_cache, [], config, ticks=3)
        db_with = r_cache.state.databases["db"].active_connections
        db_without = r_nocache.state.databases["db"].active_connections
        self.assertLess(db_with, db_without, "cache should reduce DB queries")

    def test_hit_and_miss_events_emitted(self) -> None:
        state, config = build_cluster(users=1000, with_cache=True)
        result = step(state, [], config, ticks=2)
        types = {e.type.value for e in result.events}
        self.assertIn("CACHE_HIT", types)
        self.assertIn("CACHE_MISS", types)

    def test_ttl_zero_disables_caching(self) -> None:
        state, config = build_cluster(users=1000, with_cache=True)
        set_ttl = make_command("ttl0", CommandType.SET_REDIS_CONFIG, "cache", ttl_ticks=0)
        result = step(state, [set_ttl], config, ticks=2)
        self.assertEqual(result.state.caches["cache"].hit_rate, 0.0)

    def test_low_base_hit_rate_triggers_incident(self) -> None:
        state, config = build_cluster(users=1000, with_cache=True)
        cfg = config.with_overrides({"cache_base_hit_rate": 0.4})
        result = step(state, [], cfg, ticks=4)
        keys = list(result.state.incidents.active.keys())
        self.assertTrue(
            any("CACHE_MISS_SPIKE" in k for k in keys),
            f"expected cache miss incident, got {keys}",
        )


if __name__ == "__main__":
    unittest.main()

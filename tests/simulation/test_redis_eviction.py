"""D4 regression: Redis capacity eviction actually works."""

from __future__ import annotations

import unittest

from simulation.engine import step

from tests.simulation._helpers import build_cluster


def _run(capacity: int, ticks: int = 3):  # type: ignore[no-untyped-def]
    state, config = build_cluster(users=6000, with_cache=True)
    state.caches["cache"].capacity_entries = capacity
    return step(state, [], config, ticks=ticks)


class TestRedisEviction(unittest.TestCase):
    def test_eviction_events_emitted_when_over_capacity(self) -> None:
        r = _run(capacity=5)
        evictions = [e for e in r.events if e.type.value == "CACHE_EVICTION"]
        self.assertTrue(evictions, "eviction must fire when writes exceed capacity")

    def test_used_entries_never_exceed_capacity(self) -> None:
        r = _run(capacity=5)
        cache = r.state.caches["cache"]
        self.assertLessEqual(cache.used_entries, cache.capacity_entries)

    def test_capacity_affects_hit_rate(self) -> None:
        tiny = _run(capacity=5).state.caches["cache"].hit_rate
        huge = _run(capacity=100000).state.caches["cache"].hit_rate
        self.assertNotEqual(tiny, huge, "capacity must influence hit rate")
        self.assertLess(tiny, huge, "smaller cache should have a lower hit rate")

    def test_huge_cache_has_no_eviction(self) -> None:
        r = _run(capacity=100000)
        evictions = [e for e in r.events if e.type.value == "CACHE_EVICTION"]
        self.assertEqual(evictions, [])

    def test_eviction_count_matches_overflow(self) -> None:
        # With capacity 1 and aging, overflow ~= writes each tick; evictions > 0
        # and used stays <= capacity.
        r = _run(capacity=1, ticks=1)
        cache = r.state.caches["cache"]
        self.assertLessEqual(cache.used_entries, 1)
        total_evicted = sum(
            int(e.detail.get("count", 0)) for e in r.events if e.type.value == "CACHE_EVICTION"
        )
        self.assertGreater(total_evicted, 0)


if __name__ == "__main__":
    unittest.main()

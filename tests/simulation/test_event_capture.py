"""D1 regression: step events survive event-log ring-buffer trimming."""

from __future__ import annotations

import unittest

from simulation.engine import step
from simulation.events import DomainEvent, DomainEventType

from tests.simulation._helpers import build_cluster


class TestEventCapture(unittest.TestCase):
    def _fill(self, state, n: int) -> None:  # type: ignore[no-untyped-def]
        for _ in range(n):
            state.events.emit(DomainEvent(0, DomainEventType.CACHE_HIT, "pad"))

    def test_new_events_returned_when_buffer_full(self) -> None:
        state, config = build_cluster(users=1000)
        state.events.max_size = 20
        self._fill(state, 20)
        result = step(state, [], config, ticks=1)
        self.assertGreater(len(result.events), 0, "new tick events must be returned even when full")

    def test_buffer_stays_bounded(self) -> None:
        state, config = build_cluster(users=1000)
        state.events.max_size = 20
        self._fill(state, 20)
        result = step(state, [], config, ticks=5)
        self.assertLessEqual(len(result.state.events.items), 20)

    def test_returned_events_have_no_duplicates(self) -> None:
        state, config = build_cluster(users=1000)
        state.events.max_size = 10
        self._fill(state, 10)
        result = step(state, [], config, ticks=3)
        ids = [id(e) for e in result.events]
        self.assertEqual(len(ids), len(set(ids)), "no event object returned twice")

    def test_capture_sink_not_serialized(self) -> None:
        # After a step the sink is cleared; the state serializes without it.
        state, config = build_cluster(users=500)
        result = step(state, [], config, ticks=2)
        self.assertIsNone(result.state.events._sink)


if __name__ == "__main__":
    unittest.main()

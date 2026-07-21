from __future__ import annotations

import unittest

from simulation.clock import Clock
from simulation.commands import CommandType
from simulation.engine import step
from tests.simulation._helpers import build_cluster, make_command


class TestClock(unittest.TestCase):
    def test_pause_freezes_state(self) -> None:
        state, config = build_cluster(users=100)
        state.clock.set_paused(True)
        before = state.clock.tick
        result = step(state, [], config, ticks=5)
        self.assertEqual(result.state.clock.tick, before, "paused clock must not advance")

    def test_speed_zero_is_paused(self) -> None:
        clock = Clock(speed=1)
        clock.set_speed(0)
        self.assertTrue(clock.paused)
        self.assertFalse(clock.is_running())
        self.assertEqual(clock.ticks_for_frame(), 0)

    def test_speed_multipliers(self) -> None:
        for speed in (1, 2, 4):
            clock = Clock(speed=speed)
            self.assertEqual(clock.ticks_for_frame(), speed)

    def test_invalid_speed_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Clock(speed=3)

    def test_same_tick_count_same_result(self) -> None:
        state_a, config = build_cluster(users=100)
        state_b, _ = build_cluster(users=100)
        a = step(state_a, [], config, ticks=20)
        b = step(state_b, [], config, ticks=20)
        self.assertEqual(a.state.clock.tick, b.state.clock.tick)
        self.assertEqual(a.state.to_dict(), b.state.to_dict())

    def test_set_speed_command_changes_processing(self) -> None:
        state, config = build_cluster(users=100)
        pause_cmd = make_command("pause-1", CommandType.PAUSE, paused=True)
        result = step(state, [pause_cmd], config, ticks=10)
        self.assertEqual(result.state.clock.tick, 0, "pause command must stop ticks")


if __name__ == "__main__":
    unittest.main()

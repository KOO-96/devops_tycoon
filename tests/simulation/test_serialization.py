from __future__ import annotations

import unittest

from simulation.engine import step
from simulation.serialization import clone_state, state_from_json, state_to_json
from tests.simulation._helpers import build_cluster


class TestSerialization(unittest.TestCase):
    def test_round_trip_preserves_state(self) -> None:
        state, config = build_cluster(users=500)
        advanced = step(state, [], config, ticks=15).state
        restored = state_from_json(state_to_json(advanced))
        self.assertEqual(advanced.to_dict(), restored.to_dict())

    def test_continue_after_restore_matches_uninterrupted(self) -> None:
        state, config = build_cluster(seed=3, users=800)
        cfg = config.with_overrides({"traffic_jitter": 4})

        # Uninterrupted: 40 ticks in one go.
        uninterrupted = step(state, [], cfg, ticks=40).state

        # Interrupted: 18 ticks, serialize, restore, then 22 more.
        first = step(state, [], cfg, ticks=18).state
        snapshot_json = state_to_json(first)
        restored = state_from_json(snapshot_json)
        continued = step(restored, [], cfg, ticks=22).state

        self.assertEqual(uninterrupted.to_dict(), continued.to_dict())

    def test_clone_is_independent(self) -> None:
        state, config = build_cluster(users=500)
        clone = clone_state(state)
        clone.users = 99999
        self.assertNotEqual(state.users, clone.users)

    def test_step_does_not_mutate_input(self) -> None:
        state, config = build_cluster(users=800)
        before = state_to_json(state)
        step(state, [], config, ticks=25)
        after = state_to_json(state)
        self.assertEqual(before, after, "step must not mutate the caller's state")


if __name__ == "__main__":
    unittest.main()

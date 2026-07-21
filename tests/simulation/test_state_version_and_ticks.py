"""D6/D7 regression: state version validation and tick argument validation."""

from __future__ import annotations

import json
import unittest

from simulation.engine import step
from simulation.errors import UnsupportedStateVersionError
from simulation.serialization import state_from_json, state_to_json
from simulation.state import STATE_VERSION

from tests.simulation._helpers import build_cluster


class TestStateVersion(unittest.TestCase):
    def test_current_version_loads(self) -> None:
        state, _ = build_cluster(users=100)
        restored = state_from_json(state_to_json(state))
        self.assertEqual(restored.version, STATE_VERSION)

    def test_unsupported_version_rejected(self) -> None:
        state, _ = build_cluster(users=100)
        data = json.loads(state_to_json(state))
        data["version"] = 999
        with self.assertRaises(UnsupportedStateVersionError) as ctx:
            state_from_json(json.dumps(data))
        self.assertEqual(ctx.exception.expected, STATE_VERSION)
        self.assertEqual(ctx.exception.received, 999)

    def test_missing_version_rejected(self) -> None:
        state, _ = build_cluster(users=100)
        data = json.loads(state_to_json(state))
        del data["version"]
        with self.assertRaises(UnsupportedStateVersionError):
            state_from_json(json.dumps(data))


class TestTickValidation(unittest.TestCase):
    def test_negative_ticks_raise(self) -> None:
        state, config = build_cluster(users=100)
        with self.assertRaises(ValueError):
            step(state, [], config, ticks=-1)

    def test_zero_ticks_no_advance(self) -> None:
        state, config = build_cluster(users=100)
        result = step(state, [], config, ticks=0)
        self.assertEqual(result.state.clock.tick, 0)

    def test_paused_positive_ticks_no_advance(self) -> None:
        state, config = build_cluster(users=100)
        state.clock.set_paused(True)
        result = step(state, [], config, ticks=5)
        self.assertEqual(result.state.clock.tick, 0)


if __name__ == "__main__":
    unittest.main()

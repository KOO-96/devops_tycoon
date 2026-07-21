from __future__ import annotations

import unittest

from simulation.engine import step
from simulation.rng import Rng
from tests.simulation._helpers import build_cluster


class TestRng(unittest.TestCase):
    def test_same_seed_same_sequence(self) -> None:
        a = Rng.from_seed(12345)
        b = Rng.from_seed(12345)
        self.assertEqual([a._next_u64() for _ in range(10)], [b._next_u64() for _ in range(10)])

    def test_different_seed_different_sequence(self) -> None:
        a = [Rng.from_seed(1)._next_u64() for _ in range(5)]
        b = [Rng.from_seed(2)._next_u64() for _ in range(5)]
        self.assertNotEqual(a, b)

    def test_state_round_trip(self) -> None:
        rng = Rng.from_seed(999)
        for _ in range(7):
            rng._next_u64()
        restored = Rng.from_state(rng.to_state())
        self.assertEqual(rng._next_u64(), restored._next_u64())


class TestEngineReproducibility(unittest.TestCase):
    def test_same_seed_same_run(self) -> None:
        state_a, config = build_cluster(seed=7, users=200)
        state_b, _ = build_cluster(seed=7, users=200)
        cfg = config.with_overrides({"traffic_jitter": 5})
        a = step(state_a, [], cfg, ticks=30)
        b = step(state_b, [], cfg, ticks=30)
        self.assertEqual(a.state.to_dict(), b.state.to_dict())

    def test_different_seed_diverges_with_jitter(self) -> None:
        state_a, config = build_cluster(seed=1, users=200)
        state_b, _ = build_cluster(seed=2, users=200)
        cfg = config.with_overrides({"traffic_jitter": 5})
        a = step(state_a, [], cfg, ticks=30)
        b = step(state_b, [], cfg, ticks=30)
        self.assertNotEqual(
            a.state.economy.to_dict(), b.state.economy.to_dict(),
            "different seeds with jitter should diverge",
        )

    def test_no_jitter_is_seed_independent(self) -> None:
        # With jitter disabled (default), the RNG is never drawn, so the run is
        # fully deterministic regardless of seed.
        state_a, config = build_cluster(seed=1, users=200)
        state_b, _ = build_cluster(seed=2, users=200)
        a = step(state_a, [], config, ticks=20)
        b = step(state_b, [], config, ticks=20)
        self.assertEqual(a.state.economy.to_dict(), b.state.economy.to_dict())


if __name__ == "__main__":
    unittest.main()

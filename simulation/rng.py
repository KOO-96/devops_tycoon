"""Deterministic, serializable pseudo-random number generator (SplitMix64).

Why a custom PRNG instead of :mod:`random`:
- The RNG state must serialize to a single integer so it round-trips cleanly
  through JSON with the rest of the game state.
- No hidden module-global RNG; every stochastic draw goes through an explicit
  instance carried inside ``GameState`` (master-plan 4.11, sim prompt §8).

The generator is a textbook SplitMix64: fast, well-distributed, and fully
reproducible from its 64-bit state.
"""
from __future__ import annotations

from dataclasses import dataclass

_MASK64 = (1 << 64) - 1
_GAMMA = 0x9E3779B97F4A7C15
_MIX1 = 0xBF58476D1CE4E5B9
_MIX2 = 0x94D049BB133111EB


@dataclass
class Rng:
    """A SplitMix64 generator. ``state`` alone fully determines all output."""

    state: int

    @classmethod
    def from_seed(cls, seed: int) -> "Rng":
        return cls(state=seed & _MASK64)

    def _next_u64(self) -> int:
        self.state = (self.state + _GAMMA) & _MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * _MIX1) & _MASK64
        z = ((z ^ (z >> 27)) * _MIX2) & _MASK64
        return z ^ (z >> 31)

    def random(self) -> float:
        """Uniform float in [0.0, 1.0)."""
        # 53 bits of precision, matching a double's mantissa.
        return (self._next_u64() >> 11) / float(1 << 53)

    def randint(self, low: int, high: int) -> int:
        """Uniform integer in the inclusive range [low, high]."""
        if high < low:
            raise ValueError("high must be >= low")
        span = high - low + 1
        return low + (self._next_u64() % span)

    def chance(self, probability: float) -> bool:
        """True with the given probability (clamped to [0, 1])."""
        if probability <= 0.0:
            return False
        if probability >= 1.0:
            return True
        return self.random() < probability

    def to_state(self) -> int:
        return self.state

    @classmethod
    def from_state(cls, state: int) -> "Rng":
        return cls(state=state & _MASK64)

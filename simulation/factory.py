"""Convenience constructors for fresh game states.

Topologies are otherwise built by issuing player commands (ADD_NODE / CONNECT),
which is how Backend will drive the simulation.
"""
from __future__ import annotations

from simulation.clock import Clock
from simulation.config.models import BalanceConfig
from simulation.config.defaults import default_balance_config
from simulation.rng import Rng
from simulation.state import GameState


def new_state(
    simulation_id: str,
    seed: int,
    users: int = 0,
    tick_ms: int = 200,
) -> GameState:
    """Create an empty, deterministic game state."""
    return GameState(
        simulation_id=simulation_id,
        clock=Clock(tick=0, tick_ms=tick_ms, speed=1, paused=False),
        rng=Rng.from_seed(seed),
        users=users,
    )


def new_config() -> BalanceConfig:
    """Return a fresh default balance config."""
    return default_balance_config()

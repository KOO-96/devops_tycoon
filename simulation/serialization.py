"""GameState <-> JSON serialization.

The pure game state round-trips through JSON so Backend can persist and restore
it. Restoring and continuing must yield identical results to never having
stopped (sim prompt §9, §23).
"""
from __future__ import annotations

import json

from simulation.state import GameState


def state_to_json(state: GameState, *, indent: int = 0) -> str:
    return json.dumps(
        state.to_dict(),
        sort_keys=True,
        separators=(",", ":") if not indent else (", ", ": "),
        indent=indent or None,
    )


def state_from_json(text: str) -> GameState:
    return GameState.from_dict(json.loads(text))


def clone_state(state: GameState) -> GameState:
    """Deep, structural clone via the serialization round-trip."""
    return state_from_json(state_to_json(state))

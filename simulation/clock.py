"""Deterministic game clock (GD-001, master-plan 4.5 — Confirmed structure).

The clock is the *only* notion of time in the simulation. Wall-clock time never
influences results; a run is defined purely by how many ticks are processed.

- ``tick``:      current tick count (atomic simulation unit).
- ``tick_ms``:   real milliseconds per tick at 1x (Proposed value, from config).
- ``speed``:     0 = Pause, 1 = Normal, 2 = Fast, 4 = Very Fast.
                 Speed only changes how many ticks are processed per real frame;
                 it never changes the per-tick computation.
- ``paused``:    convenience flag; when True the state does not advance.

Frontend converts ``tick`` into human-friendly game time; the canonical stored
unit is always the tick.
"""
from __future__ import annotations

from dataclasses import dataclass

VALID_SPEEDS = (0, 1, 2, 4)


@dataclass
class Clock:
    tick: int = 0
    tick_ms: int = 200
    speed: int = 1
    paused: bool = False

    def __post_init__(self) -> None:
        self._validate_speed(self.speed)

    @staticmethod
    def _validate_speed(speed: int) -> None:
        if speed not in VALID_SPEEDS:
            raise ValueError(f"speed must be one of {VALID_SPEEDS}, got {speed}")

    def set_speed(self, speed: int) -> None:
        self._validate_speed(speed)
        self.speed = speed
        self.paused = speed == 0

    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def is_running(self) -> bool:
        """A pause (explicit flag or speed 0) freezes state progression."""
        return not self.paused and self.speed != 0

    def ticks_for_frame(self) -> int:
        """How many ticks a single real frame should process at current speed."""
        return 0 if not self.is_running() else self.speed

    def advance_one(self) -> int:
        """Advance exactly one tick and return the new tick value."""
        self.tick += 1
        return self.tick

    def simulation_time_ms(self) -> int:
        """Elapsed in-game milliseconds implied by the tick count (1x basis)."""
        return self.tick * self.tick_ms

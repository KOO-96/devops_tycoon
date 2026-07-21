"""Simulation exceptions."""

from __future__ import annotations


class SimulationError(Exception):
    """Base class for all simulation errors."""


class UnsupportedStateVersionError(SimulationError):
    """Raised when a serialized state's version is not supported.

    Signals to Backend that the snapshot needs migration (or is invalid),
    rather than being silently loaded.
    """

    def __init__(self, expected: int, received: int) -> None:
        self.expected = expected
        self.received = received
        super().__init__(f"unsupported state version: expected {expected}, received {received}")

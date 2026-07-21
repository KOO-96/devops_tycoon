"""DevOps Tycoon — deterministic MVP simulation foundation.

This package computes the *facts* of the game: request flow, resource usage,
incident conditions, technology effects, economy, and the evidence data the
AI CTO consumes. It is a pure domain module with NO external I/O.

Responsibility boundary (master-plan 4.17):
- Simulation:  computes state changes, incident causes, tech effects, CTO evidence.
- Backend:     API / WebSocket / persistence (NOT computed here).
- Frontend:    presentation and player input (NOT here).

Determinism contract (program-decisions.md GD-001, master-plan 4.11):
    same seed + same initial state + same command order + same tick count
    + same balance config  =>  identical result.

The single public entry point is :func:`simulation.engine.step`.
"""
from __future__ import annotations

from simulation.engine import SimulationResult, step

__all__ = ["step", "SimulationResult"]

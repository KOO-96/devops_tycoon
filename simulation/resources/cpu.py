"""CPU usage math."""

from __future__ import annotations

from simulation.nodes.base import clamp


def cpu_usage(incoming: int, request_cpu_cost: float) -> float:
    """Fraction of CPU consumed by ``incoming`` concurrent requests (0.0..1.0).

    Higher load raises utilization toward saturation; the value is clamped so it
    never exceeds 1.0 or becomes NaN/negative.
    """
    return clamp(incoming * request_cpu_cost, 0.0, 1.0)

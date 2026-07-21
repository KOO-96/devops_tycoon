"""Memory usage math.

Effective memory = persistent leak base + transient pressure from the queue.
A non-zero ``leak_base`` that grows every tick reproduces EVT-APP-002 (a slow,
monotonic climb that a restart resets).
"""

from __future__ import annotations

from simulation.nodes.base import clamp


def memory_usage(leak_base: float, queue_length: int, request_mem_cost: float) -> float:
    """Effective memory fraction (0.0..1.0)."""
    return clamp(leak_base + queue_length * request_mem_cost, 0.0, 1.0)

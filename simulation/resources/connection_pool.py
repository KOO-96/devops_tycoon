"""Database connection pool allocation."""
from __future__ import annotations

from typing import Tuple


def allocate_connections(demand: int, max_connections: int) -> Tuple[int, int]:
    """Allocate up to ``max_connections`` for ``demand`` queries this tick.

    Returns ``(active, waiting)``. When demand exceeds the pool, the excess
    waits — the mechanism behind EVT-DB-001 (pool exhaustion). Growing the pool
    admits more queries but raises DB CPU downstream (P6), computed by the
    caller from ``active``.
    """
    if demand < 0:
        demand = 0
    cap = max(0, max_connections)
    active = min(demand, cap)
    waiting = demand - active
    return active, waiting

"""Pure resource-math helpers (CPU, memory, queue, connection pool).

Each function is deterministic and side-effect free so it can be unit-tested in
isolation; the engine orchestrates them per tick.
"""

from __future__ import annotations

from simulation.resources.connection_pool import allocate_connections
from simulation.resources.cpu import cpu_usage
from simulation.resources.memory import memory_usage
from simulation.resources.queue import drain_queue

__all__ = ["cpu_usage", "memory_usage", "drain_queue", "allocate_connections"]

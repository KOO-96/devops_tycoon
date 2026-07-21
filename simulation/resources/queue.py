"""Queue drain and timeout math."""
from __future__ import annotations

from typing import Tuple


def drain_queue(
    backlog: int,
    drain_rate: int,
    timeout_ticks: int,
) -> Tuple[int, int, int]:
    """Process a per-tick backlog.

    Args:
        backlog: queued + newly arrived requests waiting at the server.
        drain_rate: max requests the server clears in one tick.
        timeout_ticks: how long a request may wait before timing out.

    Returns ``(processed, remaining_queue, timed_out)``.

    A request times out when the remaining queue is so deep that its wait would
    exceed ``timeout_ticks`` at the current drain rate; that overflow is dropped
    from the queue and counted as a timeout (EVT-DB-001 / master-plan 4.11).
    """
    if backlog < 0:
        backlog = 0
    processed = min(backlog, max(0, drain_rate))
    remaining = backlog - processed
    capacity_within_timeout = max(0, drain_rate) * max(0, timeout_ticks)
    timed_out = max(0, remaining - capacity_within_timeout)
    remaining -= timed_out
    return processed, remaining, timed_out

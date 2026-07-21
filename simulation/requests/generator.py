"""Deterministic per-tick traffic generation.

Traffic is an aggregate count derived from the user base, not a swarm of
per-request objects (sim prompt §25). A small bounded set of sample ``Request``
objects is produced for visualization/tracing.
"""
from __future__ import annotations

from typing import List

from simulation.config.models import BalanceConfig
from simulation.requests.models import Request, RequestState


def generate_count(users: int, config: BalanceConfig) -> int:
    """Number of requests generated this tick for the given user base."""
    if users <= 0:
        return 0
    rate = config.get("requests_per_user_per_tick")
    return int(users * rate)


def make_sample_requests(
    state_tick: int,
    next_id: int,
    count: int,
    config: BalanceConfig,
) -> List[Request]:
    """Build up to a few representative requests for tracing (deterministic)."""
    samples: List[Request] = []
    if count <= 0:
        return samples
    cacheable_ratio = config.get("cacheable_ratio")
    db_ratio = config.get("db_required_ratio")
    timeout_ticks = config.get_int("request_timeout_ticks")
    max_retry = config.get_int("max_retry")
    business_value = config.get("revenue_per_completed_request")
    sample_n = min(3, count)
    for i in range(sample_n):
        idx = next_id + i
        samples.append(
            Request(
                id=f"req-{idx}",
                request_type="read" if (idx % 2 == 0) else "write",
                created_tick=state_tick,
                location="users",
                cacheable=(idx % 100) < int(cacheable_ratio * 100),
                db_required=(idx % 100) < int(db_ratio * 100),
                timeout_tick=state_tick + timeout_ticks,
                max_retry=max_retry,
                business_value=business_value,
                state=RequestState.CREATED,
            )
        )
    return samples

"""Load-balancer distribution — pure, deterministic functions.

Distribution never uses randomness; given the same servers, weights, and cursor
it always produces the same split. This is where EVT-LB-001 (traffic imbalance)
is reproduced: round-robin yields an even split, while skewed weights (or a
sticky config) concentrate traffic on a subset of servers.
"""

from __future__ import annotations

from simulation.nodes.app_server import AppServer
from simulation.nodes.base import LBAlgorithm
from simulation.nodes.load_balancer import LoadBalancer


def available_targets(servers: list[AppServer]) -> list[AppServer]:
    """Only enabled, non-Down servers receive traffic (deterministic order)."""
    return [s for s in servers if s.is_available()]


def distribute(
    lb: LoadBalancer,
    servers: list[AppServer],
    total: int,
) -> tuple[dict[str, int], int]:
    """Split ``total`` requests across available servers.

    Returns ``(per_server_counts, new_rr_cursor)``. Servers not selected still
    appear in the map with 0 so imbalance is observable. If no server is
    available, an empty map is returned and the caller drops the traffic.
    """
    targets = available_targets(servers)
    if not targets or total <= 0:
        return ({s.id: 0 for s in targets}, lb.rr_cursor)

    if lb.algorithm == LBAlgorithm.ROUND_ROBIN and not lb.sticky:
        return _round_robin(targets, total, lb.rr_cursor)
    if lb.algorithm == LBAlgorithm.LEAST_CONN and not lb.sticky:
        return (_least_conn(targets, total), lb.rr_cursor)
    # WEIGHTED, or any algorithm with sticky=True, distributes by weight.
    # A sticky/miconfigured LB concentrates load -> imbalance (EVT-LB-001).
    return (_weighted(targets, total, sticky=lb.sticky), lb.rr_cursor)


def _round_robin(targets: list[AppServer], total: int, cursor: int) -> tuple[dict[str, int], int]:
    counts = {s.id: 0 for s in targets}
    n = len(targets)
    start = cursor % n
    for i in range(total):
        counts[targets[(start + i) % n].id] += 1
    return counts, (start + total) % n


def _least_conn(targets: list[AppServer], total: int) -> dict[str, int]:
    counts = {s.id: 0 for s in targets}
    # Effective load = existing queue + already-assigned this tick.
    load = {s.id: s.queue_length for s in targets}
    order = [s.id for s in targets]
    for _ in range(total):
        # Deterministic tie-break by server id order.
        chosen = min(order, key=lambda sid: (load[sid], order.index(sid)))
        counts[chosen] += 1
        load[chosen] += 1
    return counts


def _weighted(targets: list[AppServer], total: int, sticky: bool) -> dict[str, int]:
    counts = {s.id: 0 for s in targets}
    weights = {s.id: max(0.0, s.weight) for s in targets}
    if sticky:
        # Sticky sessions pin most traffic to the first available server.
        first = targets[0].id
        weights = {sid: (10.0 if sid == first else 1.0) for sid in weights}
    total_weight = sum(weights.values())
    if total_weight <= 0:
        return _round_robin(targets, total, 0)[0]
    # Largest-remainder apportionment for a deterministic integer split.
    exact = {sid: total * w / total_weight for sid, w in weights.items()}
    floors = {sid: int(val) for sid, val in exact.items()}
    assigned = sum(floors.values())
    remainder = total - assigned
    order = sorted(
        exact.keys(),
        key=lambda sid: (-(exact[sid] - floors[sid]), sid),
    )
    for i in range(remainder):
        floors[order[i % len(order)]] += 1
    return {sid: floors[sid] for sid in counts}


def imbalance_metric(per_server: dict[str, int]) -> float:
    """Max-minus-min share across servers (0.0 = perfectly even)."""
    if not per_server:
        return 0.0
    total = sum(per_server.values())
    if total <= 0:
        return 0.0
    shares = [c / total for c in per_server.values()]
    return max(shares) - min(shares)

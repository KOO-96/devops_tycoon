"""Shared node enums and helpers.

Node health uses the four-level scale from master-plan 4.9:
``Healthy / Warning / Critical / Down``.
"""

from __future__ import annotations

from enum import StrEnum


class NodeKind(StrEnum):
    LOAD_BALANCER = "load_balancer"
    APP_SERVER = "app_server"
    REDIS = "redis"
    POSTGRESQL = "postgresql"


class Health(StrEnum):
    HEALTHY = "Healthy"
    WARNING = "Warning"
    CRITICAL = "Critical"
    DOWN = "Down"


class LBAlgorithm(StrEnum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_CONN = "least_conn"


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into [low, high]; also neutralizes NaN to ``low``.

    Guards the invariant that resource fractions never become NaN/Infinity or
    escape their valid range (sim prompt §10).
    """
    if value != value:  # NaN check
        return low
    if value < low:
        return low
    if value > high:
        return high
    return value

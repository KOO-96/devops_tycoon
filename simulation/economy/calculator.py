"""Per-tick economy: revenue from completed requests, cost from running nodes."""

from __future__ import annotations

from simulation.config.models import BalanceConfig
from simulation.state import GameState


def apply_economy(state: GameState, completed: int, config: BalanceConfig) -> None:
    """Update revenue, cost, and cash for the current tick.

    Cash may go negative (bankruptcy is a game-over condition handled elsewhere,
    master-plan 4.15); this function only accounts, it does not judge.
    """
    revenue = completed * config.get("revenue_per_completed_request")

    cost = 0.0
    cost += len(state.app_servers) * config.get("app_server_cost_per_tick")
    cost += len(state.databases) * config.get("db_cost_per_tick")
    cost += sum(1 for c in state.caches.values() if c.enabled) * config.get("cache_cost_per_tick")

    state.economy.revenue_last_tick = revenue
    state.economy.cost_last_tick = cost
    state.economy.revenue_total += revenue
    state.economy.cost_total += cost
    state.economy.cash += revenue - cost

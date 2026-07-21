"""Default balance values for the MVP simulation foundation.

Sources:
- ``program-decisions.md`` — Confirmed decisions (GD-001, EVT-D-*).
- ``events/mvp-event-catalog.md`` — Proposed per-event thresholds.

IMPORTANT: absolute time/threshold numbers are **Proposed** (playtest-tunable),
except where Program has Confirmed them (e.g. DB Connection Warning 80%, and the
*structure* of GD-001). Do not treat Proposed numbers as final.
"""
from __future__ import annotations

from simulation.config.models import BalanceConfig, BalanceValue, ValueStatus

_PD = "program-decisions.md"
_CAT = "events/mvp-event-catalog.md"

_C = ValueStatus.CONFIRMED
_P = ValueStatus.PROPOSED


def _defaults() -> "dict[str, BalanceValue]":
    v = BalanceValue
    return {
        # --- Time (GD-001: structure Confirmed, numbers Proposed) ---
        "tick_ms": v(200, "ms", _P, _PD, related_event_id="GD-001"),
        "ticks_per_game_day": v(300, "tick", _P, _PD, related_event_id="GD-001"),
        "response_window_short": v(30, "tick", _P, _PD, related_event_id="EVT-D-004"),
        "response_window_normal": v(90, "tick", _P, _PD, related_event_id="EVT-D-004"),
        "response_window_long": v(300, "tick", _P, _PD, related_event_id="EVT-D-004"),
        "cooldown_general": v(600, "tick", _P, _PD, related_event_id="EVT-D-004"),
        "cooldown_rare": v(3000, "tick", _P, _PD, related_event_id="EVT-EXT-002"),
        "max_chain_depth": v(4, "count", _C, _PD, related_event_id="EVT-D-008"),
        # --- Traffic ---
        # users -> requests-per-tick factor, and per-request costs.
        "requests_per_user_per_tick": v(0.05, "req/user/tick", _P, _CAT),
        "request_cpu_cost": v(0.02, "cpu_fraction", _P, _CAT),
        "request_mem_cost": v(0.005, "mem_fraction", _P, _CAT),
        "cacheable_ratio": v(0.6, "ratio", _P, _CAT),
        "db_required_ratio": v(0.7, "ratio", _P, _CAT),
        # Seed-driven per-tick traffic jitter amplitude (0 = deterministic, no
        # RNG draw). When > 0 the RNG is consumed, so different seeds diverge.
        "traffic_jitter": v(0, "count", _P, _CAT),
        # --- App server (EVT-APP-001/002) ---
        "app_cpu_warning": v(0.70, "ratio", _P, _CAT, operator=">=", related_event_id="EVT-APP-001"),
        "app_cpu_critical": v(0.90, "ratio", _P, _CAT, operator=">=", related_event_id="EVT-APP-001"),
        "app_cpu_recover": v(0.60, "ratio", _P, _CAT, operator="<=", related_event_id="EVT-APP-001"),
        "app_mem_warning": v(0.75, "ratio", _P, _CAT, operator=">=", related_event_id="EVT-APP-002"),
        "app_mem_critical": v(0.90, "ratio", _P, _CAT, operator=">=", related_event_id="EVT-APP-002"),
        "app_mem_recover": v(0.70, "ratio", _P, _CAT, operator="<=", related_event_id="EVT-APP-002"),
        "app_queue_drain_per_tick": v(20, "req/tick", _P, _CAT),
        # --- Load balancer (EVT-LB-001) ---
        "lb_imbalance_warning": v(0.20, "ratio_pp", _P, _CAT, operator=">=", related_event_id="EVT-LB-001"),
        "lb_imbalance_trigger": v(0.40, "ratio_pp", _P, _CAT, operator=">=", related_event_id="EVT-LB-001"),
        "lb_imbalance_recover": v(0.15, "ratio_pp", _P, _CAT, operator="<=", related_event_id="EVT-LB-001"),
        # --- Redis (EVT-CACHE-001) ---
        "cache_hit_trigger": v(0.70, "ratio", _P, _CAT, operator="<=", related_event_id="EVT-CACHE-001"),
        "cache_hit_target": v(0.90, "ratio", _P, _CAT, operator=">=", related_event_id="EVT-CACHE-001"),
        "cache_base_hit_rate": v(0.85, "ratio", _P, _CAT),
        # --- PostgreSQL connection pool (EVT-DB-001) ---
        "db_conn_warning": v(0.80, "ratio", _C, _PD, operator=">=", related_event_id="EVT-DB-001"),
        "db_conn_critical": v(0.95, "ratio", _P, _CAT, operator=">=", related_event_id="EVT-DB-001"),
        "db_conn_recover": v(0.70, "ratio", _P, _CAT, operator="<=", related_event_id="EVT-DB-001"),
        "db_cpu_per_active_conn": v(0.03, "cpu_fraction", _P, _CAT),
        "db_cpu_warning": v(0.70, "ratio", _P, _CAT, operator=">=", related_event_id="EVT-DB-002"),
        "db_cpu_critical": v(0.90, "ratio", _P, _CAT, operator=">=", related_event_id="EVT-DB-002"),
        "db_cpu_recover": v(0.60, "ratio", _P, _CAT, operator="<=", related_event_id="EVT-DB-002"),
        "db_query_ticks": v(1, "tick", _P, _CAT),
        # --- Timeout / retry (EVT-DEP/DB, master-plan 4.11) ---
        "request_timeout_ticks": v(30, "tick", _P, _CAT, related_event_id="EVT-DB-001"),
        "timeout_warn_rate": v(0.05, "ratio", _P, _CAT, operator=">=", related_event_id="EVT-DB-001"),
        "timeout_critical_rate": v(0.15, "ratio", _P, _CAT, operator=">=", related_event_id="EVT-DB-001"),
        "timeout_clear_rate": v(0.01, "ratio", _P, _CAT, operator="<=", related_event_id="EVT-DB-001"),
        "max_retry": v(2, "count", _P, _CAT),
        "retry_backoff_ticks": v(5, "tick", _P, _CAT),
        # Bounds retried requests re-entering the system, preventing retry storms.
        "retry_fraction": v(0.5, "ratio", _P, _CAT),
        "retry_ceiling": v(500, "count", _P, _CAT),
        # --- Economy ---
        "revenue_per_completed_request": v(0.01, "cash", _P, _CAT),
        "app_server_cost_per_tick": v(0.5, "cash/tick", _P, _CAT),
        "db_cost_per_tick": v(0.8, "cash/tick", _P, _CAT),
        "cache_cost_per_tick": v(0.3, "cash/tick", _P, _CAT),
        # --- Trust (EVT-D-005: per-event delta capped to avoid collapse) ---
        "trust_loss_per_incident_tick": v(0.05, "trust", _P, _PD, related_event_id="EVT-D-005"),
        "trust_loss_cap_per_incident": v(5.0, "trust", _P, _PD, related_event_id="EVT-D-005"),
        "trust_gain_on_recover": v(1.0, "trust", _P, _PD),
    }


def default_balance_config() -> BalanceConfig:
    """Return a fresh default BalanceConfig (safe to mutate via with_overrides)."""
    return BalanceConfig(values=dict(_defaults()))

"""Incident detection rules — pure signal collection from observable state.

Each rule yields an :class:`IncidentSignal` describing, for one (type, target),
whether the warning / critical thresholds are met and whether the condition has
cleared. All thresholds come from BalanceConfig (never hardcoded).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.config.models import BalanceConfig
from simulation.incidents.models import IncidentType
from simulation.requests.models import TickTraffic

if TYPE_CHECKING:
    from simulation.state import GameState


@dataclass
class IncidentSignal:
    type: IncidentType
    target: str
    metric: float
    warning: bool
    critical: bool
    cleared: bool


def collect_signals(
    state: GameState,
    traffic: TickTraffic,
    config: BalanceConfig,
) -> list[IncidentSignal]:
    signals: list[IncidentSignal] = []
    _app_cpu_signals(state, config, signals)
    _app_mem_signals(state, config, signals)
    _db_pool_signals(state, config, signals)
    _db_cpu_signals(state, config, signals)
    _cache_signals(state, config, signals)
    _timeout_signal(state, traffic, config, signals)
    _lb_imbalance_signals(state, traffic, config, signals)
    _no_healthy_server_signals(state, traffic, signals)
    return signals


def _app_cpu_signals(state: GameState, cfg: BalanceConfig, out: list[IncidentSignal]) -> None:
    warn, crit, rec = (
        cfg.get("app_cpu_warning"),
        cfg.get("app_cpu_critical"),
        cfg.get("app_cpu_recover"),
    )
    for sid, s in state.app_servers.items():
        cpu = s.cpu_usage
        out.append(
            IncidentSignal(
                IncidentType.APP_CPU_OVERLOAD,
                sid,
                cpu,
                warning=cpu >= warn,
                critical=cpu >= crit,
                cleared=cpu <= rec,
            )
        )


def _app_mem_signals(state: GameState, cfg: BalanceConfig, out: list[IncidentSignal]) -> None:
    warn, crit, rec = (
        cfg.get("app_mem_warning"),
        cfg.get("app_mem_critical"),
        cfg.get("app_mem_recover"),
    )
    for sid, s in state.app_servers.items():
        mem = s.mem_usage
        out.append(
            IncidentSignal(
                IncidentType.APP_MEM_SATURATION,
                sid,
                mem,
                warning=mem >= warn,
                critical=mem >= crit,
                cleared=mem <= rec,
            )
        )


def _db_pool_signals(state: GameState, cfg: BalanceConfig, out: list[IncidentSignal]) -> None:
    warn, crit, rec = (
        cfg.get("db_conn_warning"),
        cfg.get("db_conn_critical"),
        cfg.get("db_conn_recover"),
    )
    for did, db in state.databases.items():
        ratio = db.connection_ratio()
        out.append(
            IncidentSignal(
                IncidentType.DB_CONNECTION_POOL_EXHAUSTION,
                did,
                ratio,
                warning=ratio >= warn,
                critical=ratio >= crit,
                cleared=ratio <= rec,
            )
        )


def _db_cpu_signals(state: GameState, cfg: BalanceConfig, out: list[IncidentSignal]) -> None:
    warn, crit, rec = (
        cfg.get("db_cpu_warning"),
        cfg.get("db_cpu_critical"),
        cfg.get("db_cpu_recover"),
    )
    for did, db in state.databases.items():
        cpu = db.cpu_usage
        out.append(
            IncidentSignal(
                IncidentType.DB_CPU_SATURATION,
                did,
                cpu,
                warning=cpu >= warn,
                critical=cpu >= crit,
                cleared=cpu <= rec,
            )
        )


def _cache_signals(state: GameState, cfg: BalanceConfig, out: list[IncidentSignal]) -> None:
    trigger, target = cfg.get("cache_hit_trigger"), cfg.get("cache_hit_target")
    warn_level = (trigger + target) / 2.0
    for cid, cache in state.caches.items():
        if not cache.enabled:
            continue
        hit = cache.hit_rate
        out.append(
            IncidentSignal(
                IncidentType.CACHE_MISS_SPIKE,
                cid,
                hit,
                warning=hit <= warn_level,
                critical=hit <= trigger,
                cleared=hit >= target,
            )
        )


def _timeout_signal(
    state: GameState, traffic: TickTraffic, cfg: BalanceConfig, out: list[IncidentSignal]
) -> None:
    routed = max(1, traffic.routed)
    rate = traffic.timed_out / routed
    out.append(
        IncidentSignal(
            IncidentType.REQUEST_TIMEOUT,
            "system",
            rate,
            warning=rate >= cfg.get("timeout_warn_rate"),
            critical=rate >= cfg.get("timeout_critical_rate"),
            cleared=rate <= cfg.get("timeout_clear_rate"),
        )
    )


def _lb_imbalance_signals(
    state: GameState, traffic: TickTraffic, cfg: BalanceConfig, out: list[IncidentSignal]
) -> None:
    warn, crit, rec = (
        cfg.get("lb_imbalance_warning"),
        cfg.get("lb_imbalance_trigger"),
        cfg.get("lb_imbalance_recover"),
    )
    per_server = traffic.per_server_routed or {}
    if len(per_server) < 2:
        return
    total = sum(per_server.values())
    if total <= 0:
        return
    shares = [c / total for c in per_server.values()]
    metric = max(shares) - min(shares)
    for lb_id in state.load_balancers:
        out.append(
            IncidentSignal(
                IncidentType.LB_IMBALANCE,
                lb_id,
                metric,
                warning=metric >= warn,
                critical=metric >= crit,
                cleared=metric <= rec,
            )
        )


def _no_healthy_server_signals(
    state: GameState, traffic: TickTraffic, out: list[IncidentSignal]
) -> None:
    for lb_id in state.load_balancers:
        servers = state.app_servers_behind(lb_id)
        available = [s for s in servers if s.is_available()]
        has_demand = traffic.generated > 0
        none_available = len(servers) > 0 and len(available) == 0
        out.append(
            IncidentSignal(
                IncidentType.NO_HEALTHY_SERVER,
                lb_id,
                float(len(available)),
                warning=none_available,
                critical=none_available and has_demand,
                cleared=len(available) >= 1,
            )
        )

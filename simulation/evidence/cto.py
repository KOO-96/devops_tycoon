"""CTO evidence: the structured, fact-only basis the AI CTO reasons from.

Boundary (master-plan 4.12, P8): the simulation states *facts*; it separates
confirmed facts from hypotheses and lists what is NOT observable, so the CTO
never asserts an unobserved root cause as certain. Candidate causes/actions are
drawn from the approved technology-trigger-matrix and always flagged as
hypotheses, never as confirmed truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from simulation.incidents.models import IncidentType
from simulation.metrics import MetricSnapshot
from simulation.state import GameState

# Candidate causes and actions per incident type, sourced from
# events/technology-trigger-matrix.md. These are HYPOTHESES, not confirmed facts.
_HYPOTHESES: Dict[IncidentType, List[str]] = {
    IncidentType.LB_IMBALANCE: [
        "LB algorithm/weights skewed",
        "sticky sessions concentrating traffic",
        "health check wrongly excluding a server",
    ],
    IncidentType.APP_CPU_OVERLOAD: [
        "traffic exceeds current app capacity",
        "inefficient request handling",
    ],
    IncidentType.APP_MEM_SATURATION: [
        "memory leak (monotonic growth)",
        "insufficient memory for concurrency",
    ],
    IncidentType.DB_CONNECTION_POOL_EXHAUSTION: [
        "app scale-out raised total connections (derived bottleneck)",
        "long-held transactions",
        "pool too small for demand",
    ],
    IncidentType.DB_CPU_SATURATION: [
        "pool enlarged, pushing load onto DB CPU (derived bottleneck)",
        "slow query / missing index",
    ],
    IncidentType.CACHE_MISS_SPIKE: [
        "TTL too short or key design",
        "cache capacity eviction",
    ],
    IncidentType.REQUEST_TIMEOUT: [
        "downstream bottleneck (DB/pool) inflating latency",
        "insufficient processing capacity",
    ],
    IncidentType.NO_HEALTHY_SERVER: [
        "all app servers down or excluded",
        "health check misconfiguration",
    ],
}

_ACTIONS: Dict[IncidentType, List[Dict[str, str]]] = {
    IncidentType.LB_IMBALANCE: [
        {"action": "change LB algorithm to round-robin/least-conn", "risk": "brief redistribution latency"},
        {"action": "disable sticky sessions", "risk": "session-affinity features affected"},
        {"action": "add a server", "risk": "cost up; does not fix misconfiguration"},
    ],
    IncidentType.APP_CPU_OVERLOAD: [
        {"action": "scale out app servers", "risk": "cost up; may exhaust DB connections (P6)"},
        {"action": "optimize hot path", "risk": "dev time"},
        {"action": "rate limit", "risk": "user experience / revenue"},
    ],
    IncidentType.APP_MEM_SATURATION: [
        {"action": "rolling restart", "risk": "temporary; recurs if leak"},
        {"action": "ship leak fix", "risk": "deploy risk (EVT-DEP-001)"},
    ],
    IncidentType.DB_CONNECTION_POOL_EXHAUSTION: [
        {"action": "enlarge pool", "risk": "raises DB CPU -> slow query (P6)"},
        {"action": "add cache to cut DB reads", "risk": "stale/stampede risk"},
        {"action": "rate limit", "risk": "user experience"},
    ],
    IncidentType.DB_CPU_SATURATION: [
        {"action": "add index / optimize query", "risk": "dev time; write cost"},
        {"action": "cache results", "risk": "staleness"},
    ],
    IncidentType.CACHE_MISS_SPIKE: [
        {"action": "tune TTL / key design", "risk": "over-long TTL -> stale"},
        {"action": "increase cache memory", "risk": "cost up"},
    ],
    IncidentType.REQUEST_TIMEOUT: [
        {"action": "resolve downstream bottleneck", "risk": "depends on true cause"},
        {"action": "add capacity", "risk": "cost up"},
    ],
    IncidentType.NO_HEALTHY_SERVER: [
        {"action": "restart / add standby server", "risk": "recovery time; cost"},
        {"action": "fix health check thresholds", "risk": "transient instability during retune"},
    ],
}


@dataclass
class CTOEvidence:
    tick: int
    observable_metrics: Dict[str, object] = field(default_factory=dict)
    active_alerts: List[Dict[str, object]] = field(default_factory=list)
    confirmed_facts: List[str] = field(default_factory=list)
    hypotheses: List[str] = field(default_factory=list)
    unavailable_information: List[str] = field(default_factory=list)
    possible_actions: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "tick": self.tick,
            "observable_metrics": self.observable_metrics,
            "active_alerts": self.active_alerts,
            "confirmed_facts": self.confirmed_facts,
            "hypotheses": self.hypotheses,
            "unavailable_information": self.unavailable_information,
            "possible_actions": self.possible_actions,
        }


def build_cto_evidence(state: GameState, snapshot: MetricSnapshot) -> CTOEvidence:
    evidence = CTOEvidence(tick=state.clock.tick)
    evidence.observable_metrics = {
        "traffic": snapshot.traffic,
        "app_servers": snapshot.app_servers,
        "databases": snapshot.databases,
        "caches": snapshot.caches,
        "cash": snapshot.cash,
    }
    for incident in state.incidents.active.values():
        evidence.active_alerts.append(
            {
                "incident": incident.type.value,
                "target": incident.target,
                "phase": incident.phase.value,
                "metric": incident.metric,
                "event_id": incident.event_id,
            }
        )
        # A confirmed fact is only the *observed measurement*, not the cause.
        evidence.confirmed_facts.append(
            f"{incident.type.value} on {incident.target}: metric={incident.metric:.3f}, "
            f"phase={incident.phase.value}"
        )
        for hypothesis in _HYPOTHESES.get(incident.type, []):
            tagged = f"[{incident.target}] {hypothesis}"
            if tagged not in evidence.hypotheses:
                evidence.hypotheses.append(tagged)
        for action in _ACTIONS.get(incident.type, []):
            evidence.possible_actions.append({**action, "for": incident.target})

    # Explicitly mark what the simulation does NOT expose as observable, so the
    # CTO cannot present these as confirmed.
    evidence.unavailable_information = [
        "exact root cause (must be inferred from observable metrics)",
        "future traffic beyond announced events",
        "internal code-level detail (e.g. precise leaking allocation site)",
    ]
    return evidence

"""Incident state-machine transitions.

Transitions (sim prompt §19):
    (none) --warning--> WARNING --critical--> ACTIVE --cleared--> RECOVERING
            --cleared--> RECOVERED --> removed (+ cooldown blocks re-arm)

An incident always passes through WARNING before ACTIVE, guaranteeing an
observable warning sign precedes every failure (P7). One incident per
(type, target) key prevents duplicate spam every tick.
"""

from __future__ import annotations

from simulation.config.models import BalanceConfig
from simulation.events import DomainEvent, DomainEventType, EventLog
from simulation.incidents.models import (
    INCIDENT_EVENT_ID,
    Incident,
    IncidentBook,
    IncidentPhase,
    incident_key,
)
from simulation.incidents.rules import IncidentSignal


def evaluate_incidents(
    book: IncidentBook,
    signals: list[IncidentSignal],
    tick: int,
    config: BalanceConfig,
    events: EventLog,
) -> None:
    cooldown = config.get_int("cooldown_general")
    for signal in signals:
        key = incident_key(signal.type, signal.target)
        existing = book.active.get(key)
        if existing is None:
            _maybe_open(book, signal, key, tick, cooldown, events)
        else:
            _advance(book, existing, signal, key, tick, cooldown, events)


def _maybe_open(
    book: IncidentBook,
    signal: IncidentSignal,
    key: str,
    tick: int,
    cooldown: int,
    events: EventLog,
) -> None:
    if not signal.warning or signal.cleared:
        return
    if tick < book.cooldown_until.get(key, 0):
        return
    incident = Incident(
        type=signal.type,
        target=signal.target,
        phase=IncidentPhase.WARNING,
        opened_tick=tick,
        updated_tick=tick,
        warning_since_tick=tick,
        metric=signal.metric,
        event_id=INCIDENT_EVENT_ID.get(signal.type, ""),
    )
    book.active[key] = incident
    events.emit(
        DomainEvent(
            tick=tick,
            type=DomainEventType.INCIDENT_OPENED,
            target=signal.target,
            detail={
                "incident": signal.type.value,
                "phase": incident.phase.value,
                "metric": signal.metric,
                "event_id": incident.event_id,
            },
        )
    )


def _advance(
    book: IncidentBook,
    incident: Incident,
    signal: IncidentSignal,
    key: str,
    tick: int,
    cooldown: int,
    events: EventLog,
) -> None:
    incident.metric = signal.metric
    incident.updated_tick = tick
    old_phase = incident.phase
    new_phase = _next_phase(old_phase, signal)

    if new_phase == old_phase:
        return

    if new_phase is None:
        # RECOVERED -> remove and start cooldown.
        del book.active[key]
        book.cooldown_until[key] = tick + cooldown
        events.emit(
            DomainEvent(
                tick=tick,
                type=DomainEventType.INCIDENT_RESOLVED,
                target=incident.target,
                detail={"incident": incident.type.value, "event_id": incident.event_id},
            )
        )
        return

    incident.phase = new_phase
    events.emit(
        DomainEvent(
            tick=tick,
            type=DomainEventType.INCIDENT_PHASE_CHANGED,
            target=incident.target,
            detail={
                "incident": incident.type.value,
                "from": old_phase.value,
                "to": new_phase.value,
                "metric": signal.metric,
            },
        )
    )


def _next_phase(phase: IncidentPhase, signal: IncidentSignal) -> IncidentPhase | None:
    """Return the next phase, or None when the incident should be removed."""
    if phase == IncidentPhase.WARNING:
        if signal.critical:
            return IncidentPhase.ACTIVE
        if signal.cleared:
            return None  # never escalated; resolve immediately
        return IncidentPhase.WARNING
    if phase == IncidentPhase.ACTIVE:
        if signal.cleared:
            return IncidentPhase.RECOVERING
        return IncidentPhase.ACTIVE
    if phase == IncidentPhase.RECOVERING:
        if signal.critical:
            return IncidentPhase.ACTIVE
        if signal.cleared:
            return IncidentPhase.RECOVERED
        return IncidentPhase.RECOVERING
    # RECOVERED
    return None

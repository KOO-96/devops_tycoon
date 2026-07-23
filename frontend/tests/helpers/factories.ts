import type { EventEnvelope, SessionSummary, SimulationSnapshot } from '../../src/api/schemas';

let cursorSeq = 100;

export function makeEvent(overrides: Partial<EventEnvelope> = {}): EventEnvelope {
  const cursor = overrides.cursor ?? cursorSeq++;
  return {
    event_id: overrides.event_id ?? `evt-${cursor}`,
    cursor,
    session_id: overrides.session_id ?? 'sess-1',
    session_revision: overrides.session_revision ?? 1,
    tick: overrides.tick ?? 10,
    type: overrides.type ?? 'REQUEST_COMPLETED',
    target: overrides.target ?? null,
    payload: overrides.payload ?? {},
  };
}

export function wsDomainEvent(event: EventEnvelope): Record<string, unknown> {
  return {
    protocol_version: 1,
    message_type: 'DOMAIN_EVENT',
    session_id: event.session_id,
    cursor: event.cursor,
    payload: event,
  };
}

export function makeSummary(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    session_id: 'sess-1',
    status: 'ACTIVE',
    revision: 0,
    current_tick: 0,
    speed: 1,
    paused: false,
    economy: { cash: 1000, revenue_total: 0, cost_total: 0 },
    user_trust: 100,
    investor_trust: 100,
    active_incidents: [],
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

export function makeSnapshot(overrides: Partial<SimulationSnapshot> = {}): SimulationSnapshot {
  return {
    version: 2,
    simulation_id: 'sess-1',
    clock: { tick: 0, tick_ms: 1000, speed: 1, paused: false },
    load_balancers: {},
    app_servers: {
      'app-1': { id: 'app-1', kind: 'app_server', enabled: true, health: 'Healthy', cpu_usage: 10 },
    },
    caches: {},
    databases: {},
    connections: [],
    ...overrides,
  };
}

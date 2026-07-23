import { beforeEach, describe, expect, it } from 'vitest';
import { useGameSessionStore } from '../../src/state/gameSessionStore';
import { makeEvent, makeSnapshot, makeSummary } from '../helpers/factories';

const store = useGameSessionStore;

describe('gameSessionStore', () => {
  beforeEach(() => store.getState().reset());

  it('keeps revision, tick, and state_version distinct', () => {
    store.getState().initFromCreate({
      session_id: 's',
      status: 'ACTIVE',
      revision: 0,
      current_tick: 0,
      state_version: 2,
      created_at: 'now',
    });
    store.getState().setSnapshot({
      session_id: 's',
      revision: 3,
      simulation_state_version: 2,
      snapshot: makeSnapshot({ clock: { tick: 42, tick_ms: 1000, speed: 1, paused: false } }),
    });
    const s = store.getState();
    expect(s.revision).toBe(3);
    expect(s.currentTick).toBe(42);
    expect(s.stateVersion).toBe(2);
  });

  it('never moves revision or tick backwards on summary refresh', () => {
    store.setState({ revision: 5, currentTick: 40 });
    store.getState().setSummary(makeSummary({ revision: 2, current_tick: 10 }));
    expect(store.getState().revision).toBe(5);
    expect(store.getState().currentTick).toBe(40);
  });

  it('applies events once, dedupes by event_id, advances cursor', () => {
    const e = makeEvent({ cursor: 7, event_id: 'a', tick: 12, session_revision: 3 });
    expect(store.getState().applyEvent(e)).toBe(true);
    expect(store.getState().applyEvent(e)).toBe(false); // duplicate
    const s = store.getState();
    expect(s.lastProcessedCursor).toBe(7);
    expect(s.currentTick).toBe(12);
    expect(s.revision).toBe(3);
    expect(s.events).toHaveLength(1);
  });

  it('ignores an already-delivered (stale) cursor', () => {
    store.getState().applyEvent(makeEvent({ cursor: 10, event_id: 'a' }));
    expect(store.getState().applyEvent(makeEvent({ cursor: 5, event_id: 'b' }))).toBe(false);
  });

  it('tracks selection and pending commands', () => {
    store.getState().select('app-1');
    expect(store.getState().selectedNodeId).toBe('app-1');
    store.getState().beginPending({ key: 'k', commandId: 'c', commandType: 'PAUSE', payload: {}, status: 'in_flight' });
    expect(store.getState().isPending('k')).toBe(true);
    store.getState().clearPending('k');
    expect(store.getState().isPending('k')).toBe(false);
  });

  it('stale guard: an older snapshot never overwrites a newer one (§5)', () => {
    store.getState().setSnapshot({
      session_id: 's',
      revision: 4,
      simulation_state_version: 2,
      snapshot: makeSnapshot({ app_servers: { 'app-4': { id: 'app-4', kind: 'app_server', enabled: true, health: 'Healthy' } } }),
    });
    // A late revision-3 snapshot arrives after revision 4 -> discarded.
    store.getState().setSnapshot({
      session_id: 's',
      revision: 3,
      simulation_state_version: 2,
      snapshot: makeSnapshot({ app_servers: {} }),
    });
    expect(store.getState().revision).toBe(4);
    expect(Object.keys(store.getState().snapshot!.app_servers)).toContain('app-4');
  });

  it('stale guard: an older summary is ignored', () => {
    store.getState().setSummary(makeSummary({ revision: 4, current_tick: 40 }));
    store.getState().setSummary(makeSummary({ revision: 3, current_tick: 10, speed: 4 }));
    expect(store.getState().revision).toBe(4);
    expect(store.getState().summary?.speed).toBe(1); // the rev-4 summary, not the stale rev-3
  });

  it('clears a selection that no longer exists after a snapshot update (§8)', () => {
    store.getState().setSnapshot({
      session_id: 's', revision: 1, simulation_state_version: 2,
      snapshot: makeSnapshot({ app_servers: { 'app-1': { id: 'app-1', kind: 'app_server', enabled: true, health: 'Healthy' } } }),
    });
    store.getState().select('app-1');
    // A newer snapshot without app-1.
    store.getState().setSnapshot({
      session_id: 's', revision: 2, simulation_state_version: 2,
      snapshot: makeSnapshot({ app_servers: {} }),
    });
    expect(store.getState().selectedNodeId).toBeNull();
  });

  it('beginLoad resets state and enters loading for the new session/generation', () => {
    store.getState().select('old');
    store.getState().beginLoad('sess-2', 7);
    const s = store.getState();
    expect(s.loadState).toBe('loading');
    expect(s.loadGeneration).toBe(7);
    expect(s.sessionId).toBe('sess-2');
    expect(s.selectedNodeId).toBeNull();
    expect(s.snapshot).toBeNull();
  });
});

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
});

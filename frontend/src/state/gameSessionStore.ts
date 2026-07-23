/**
 * Game session UI store (§21). Holds Backend-derived data (summary, snapshot)
 * separately from UI-only state (selection, pending commands). The Backend
 * snapshot is treated as read-only and never mutated in place.
 *
 * Event application (§15) is centralized here: de-duplicate by `event_id`
 * (bounded), advance `lastProcessedCursor`, and keep a bounded display log.
 * `revision`, `current_tick`, and `state_version` are kept distinct.
 */

import { create } from 'zustand';
import { BoundedSet } from '../utils/boundedSet';
import type { ErrorCode } from '../api/errors';
import type {
  CreateSessionResponse,
  EventEnvelope,
  SessionSummary,
  SimulationSnapshot,
  SnapshotResponse,
} from '../api/schemas';

const EVENT_LOG_CAP = 200;
const RECENT_ID_CAP = 4096;

export interface UiError {
  code: ErrorCode;
  message: string;
  requestId: string;
}

export type PendingStatus = 'in_flight';

export interface PendingCommand {
  key: string;
  commandId: string;
  commandType: string;
  payload: Record<string, unknown>;
  status: PendingStatus;
}

export interface GameSessionState {
  sessionId: string | null;
  summary: SessionSummary | null;
  snapshot: SimulationSnapshot | null;
  revision: number;
  currentTick: number;
  stateVersion: number | null;
  selectedNodeId: string | null;
  events: EventEnvelope[];
  lastProcessedCursor: number;
  pending: Record<string, PendingCommand>;
  lastError: UiError | null;
  // Internal, non-reactive dedup memory (bounded — §26).
  _recentEventIds: BoundedSet<string>;

  initFromCreate: (res: CreateSessionResponse) => void;
  setSummary: (summary: SessionSummary) => void;
  setSnapshot: (res: SnapshotResponse) => void;
  select: (nodeId: string | null) => void;
  applyEvent: (event: EventEnvelope) => boolean;
  applyEvents: (events: EventEnvelope[]) => number;
  setError: (error: UiError | null) => void;
  beginPending: (command: PendingCommand) => void;
  clearPending: (key: string) => void;
  isPending: (key: string) => boolean;
  reset: () => void;
}

function freshInitial() {
  return {
    sessionId: null as string | null,
    summary: null as SessionSummary | null,
    snapshot: null as SimulationSnapshot | null,
    revision: 0,
    currentTick: 0,
    stateVersion: null as number | null,
    selectedNodeId: null as string | null,
    events: [] as EventEnvelope[],
    lastProcessedCursor: 0,
    pending: {} as Record<string, PendingCommand>,
    lastError: null as UiError | null,
    _recentEventIds: new BoundedSet<string>(RECENT_ID_CAP),
  };
}

export const useGameSessionStore = create<GameSessionState>((set, get) => ({
  ...freshInitial(),

  initFromCreate: (res) =>
    set({
      sessionId: res.session_id,
      revision: res.revision,
      currentTick: res.current_tick,
      stateVersion: res.state_version,
    }),

  setSummary: (summary) =>
    set((state) => ({
      summary,
      // Summary revision/tick may be newer than what we've seen; never go backwards.
      revision: Math.max(state.revision, summary.revision),
      currentTick: Math.max(state.currentTick, summary.current_tick),
    })),

  setSnapshot: (res) =>
    set((state) => ({
      snapshot: res.snapshot,
      stateVersion: res.simulation_state_version,
      revision: Math.max(state.revision, res.revision),
      currentTick: Math.max(state.currentTick, res.snapshot.clock?.tick ?? state.currentTick),
    })),

  select: (selectedNodeId) => set({ selectedNodeId }),

  applyEvent: (event) => {
    const state = get();
    if (state._recentEventIds.has(event.event_id)) return false;
    // Cursor is global and may have gaps; only skip when clearly already-delivered.
    if (event.cursor <= state.lastProcessedCursor && state.lastProcessedCursor > 0) {
      state._recentEventIds.add(event.event_id);
      return false;
    }
    state._recentEventIds.add(event.event_id);
    const events = [...state.events, event];
    if (events.length > EVENT_LOG_CAP) events.splice(0, events.length - EVENT_LOG_CAP);
    set({
      events,
      lastProcessedCursor: Math.max(state.lastProcessedCursor, event.cursor),
      currentTick: Math.max(state.currentTick, event.tick),
      revision: Math.max(state.revision, event.session_revision),
    });
    return true;
  },

  applyEvents: (incoming) => {
    let applied = 0;
    for (const event of incoming) {
      if (get().applyEvent(event)) applied += 1;
    }
    return applied;
  },

  setError: (lastError) => set({ lastError }),

  beginPending: (command) =>
    set((state) => ({ pending: { ...state.pending, [command.key]: command } })),

  clearPending: (key) =>
    set((state) => {
      if (!(key in state.pending)) return {};
      const pending = { ...state.pending };
      delete pending[key];
      return { pending };
    }),

  isPending: (key) => key in get().pending,

  reset: () => set({ ...freshInitial() }),
}));

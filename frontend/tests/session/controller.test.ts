import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GameSessionController, stableStringify } from '../../src/session/controller';
import { useGameSessionStore } from '../../src/state/gameSessionStore';
import { useConnectionStore } from '../../src/state/connectionStore';
import { makeSnapshot, makeSummary } from '../helpers/factories';
import { makeSocketFactory } from '../helpers/fakeSocket';
import type { SnapshotNode } from '../../src/api/schemas';

function res(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status });
}
const errBody = (code: string) => ({ error: { code, message: code, details: {}, request_id: 'r' } });

/** A tiny stateful fake backend so bootstrap + command + snapshot-refetch behave
 * realistically. */
function fakeBackend() {
  const state = {
    revision: 0,
    nodes: {} as Record<string, SnapshotNode>,
    summaryCode: null as string | null, // force an error on GET summary
    snapshotCode: null as string | null, // force an error on GET snapshot
    commandCode: null as string | null, // force an error on POST command
  };
  const snapshotBody = () => ({
    session_id: 's',
    revision: state.revision,
    simulation_state_version: 2,
    snapshot: makeSnapshot({
      app_servers: state.nodes,
      clock: { tick: state.revision, tick_ms: 1000, speed: 1, paused: false },
    }),
  });
  const fetchFn = vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    if (/\/commands$/.test(url) && method === 'POST') {
      if (state.commandCode) return Promise.resolve(res(state.commandCode === 'REVISION_CONFLICT' ? 409 : 503, errBody(state.commandCode)));
      const body = JSON.parse(String(init?.body ?? '{}'));
      // apply ADD_NODE to the fake state
      if (body.command_type === 'ADD_NODE') state.nodes[body.payload.target] = { id: body.payload.target, kind: 'app_server', enabled: true, health: 'Healthy' };
      if (body.command_type === 'REMOVE_NODE') delete state.nodes[body.payload.target];
      state.revision += 1;
      return Promise.resolve(res(200, { command_id: body.command_id, sequence: state.revision, status: 'APPLIED', reason_code: null, session_revision: state.revision, current_tick: state.revision, events: [], state_summary: {} }));
    }
    if (/\/snapshot$/.test(url)) {
      if (state.snapshotCode) return Promise.resolve(res(state.snapshotCode === 'SESSION_NOT_FOUND' ? 404 : state.snapshotCode === 'SNAPSHOT_VERSION_UNSUPPORTED' ? 422 : 503, errBody(state.snapshotCode)));
      return Promise.resolve(res(200, snapshotBody()));
    }
    if (/\/events/.test(url)) return Promise.resolve(res(200, { session_id: 's', events: [] }));
    if (/\/game-sessions\/[^/]+$/.test(url) && method === 'GET') {
      if (state.summaryCode) return Promise.resolve(res(state.summaryCode === 'SESSION_NOT_FOUND' ? 404 : 503, errBody(state.summaryCode)));
      return Promise.resolve(res(200, makeSummary({ revision: state.revision, current_tick: state.revision })));
    }
    if (/\/game-sessions$/.test(url) && method === 'POST') return Promise.resolve(res(201, { session_id: 's', status: 'ACTIVE', revision: 0, current_tick: 0, state_version: 2, created_at: 'now' }));
    throw new Error(`no route ${method} ${url}`);
  });
  return { state, fetchFn };
}

let current: GameSessionController | null = null;
function makeController(fetchFn: ReturnType<typeof vi.fn>) {
  const { factory } = makeSocketFactory();
  current = new GameSessionController({ baseWsUrl: 'ws://h', fetch: fetchFn as never, createWebSocket: factory });
  return current;
}
const g = () => useGameSessionStore.getState();

describe('GameSessionController', () => {
  beforeEach(() => {
    useGameSessionStore.getState().reset();
    useConnectionStore.getState().reset();
  });
  afterEach(() => current?.teardown());

  it('bootstrap loads summary + snapshot + events and becomes ready', async () => {
    const be = fakeBackend();
    be.state.nodes['seed-app'] = { id: 'seed-app', kind: 'app_server', enabled: true, health: 'Healthy' };
    await makeController(be.fetchFn).bootstrapSession('s');
    expect(g().loadState).toBe('ready');
    expect(g().snapshot).not.toBeNull();
    expect(g().sessionId).toBe('s');
    expect(Object.keys(g().snapshot!.app_servers)).toContain('seed-app');
  });

  it('OPS-1: ADD_NODE is reflected without reload (snapshot refetched)', async () => {
    const be = fakeBackend();
    const c = makeController(be.fetchFn);
    await c.bootstrapSession('s');
    expect(Object.keys(g().snapshot!.app_servers)).toHaveLength(0); // Nodes(0)
    const r = await c.runCommand('ADD_NODE:app-1', 'ADD_NODE', { target: 'app-1', node_kind: 'app_server' });
    expect(r?.status).toBe('APPLIED');
    expect(g().snapshotSyncState).toBe('synced');
    expect(Object.keys(g().snapshot!.app_servers)).toContain('app-1'); // Nodes(1) without reload
    expect(g().revision).toBe(1);
  });

  it('REMOVE_NODE reflects immediately and clears a stale selection', async () => {
    const be = fakeBackend();
    be.state.nodes['app-1'] = { id: 'app-1', kind: 'app_server', enabled: true, health: 'Healthy' };
    const c = makeController(be.fetchFn);
    await c.bootstrapSession('s');
    g().select('app-1');
    await c.runCommand('REMOVE_NODE:app-1', 'REMOVE_NODE', { target: 'app-1' });
    expect(Object.keys(g().snapshot!.app_servers)).not.toContain('app-1');
    expect(g().selectedNodeId).toBeNull();
  });

  it('sends expected_revision and never a sequence', async () => {
    const be = fakeBackend();
    const c = makeController(be.fetchFn);
    await c.bootstrapSession('s');
    await c.runCommand('PAUSE:on', 'PAUSE', { paused: true });
    const cmd = be.fetchFn.mock.calls.find((cc) => /\/commands$/.test(cc[0] as string))!;
    const body = JSON.parse((cmd[1] as RequestInit).body as string);
    expect(body.expected_revision).toBe(0);
    expect('sequence' in body).toBe(false);
  });

  it('snapshot-sync failure marks failed and does NOT re-send the command', async () => {
    const be = fakeBackend();
    const c = makeController(be.fetchFn);
    await c.bootstrapSession('s');
    be.state.snapshotCode = 'DATABASE_UNAVAILABLE'; // snapshot refetch after command fails
    await c.runCommand('ADD_NODE:app-1', 'ADD_NODE', { target: 'app-1', node_kind: 'app_server' });
    expect(g().snapshotSyncState).toBe('failed');
    const commandCalls = be.fetchFn.mock.calls.filter((cc) => /\/commands$/.test(cc[0] as string));
    expect(commandCalls).toHaveLength(1); // command not re-sent
  });

  it('REVISION_CONFLICT: no auto-retry, drops intent so re-issue uses a new id', async () => {
    const be = fakeBackend();
    const c = makeController(be.fetchFn);
    await c.bootstrapSession('s');
    be.state.commandCode = 'REVISION_CONFLICT';
    await c.runCommand('ADD:x', 'ADD_NODE', { target: 'x', node_kind: 'app_server' });
    expect(g().lastError?.code).toBe('REVISION_CONFLICT');
    const firstId = JSON.parse((be.fetchFn.mock.calls.find((cc) => /\/commands$/.test(cc[0] as string))![1] as RequestInit).body as string).command_id;
    be.state.commandCode = null;
    await c.runCommand('ADD:x', 'ADD_NODE', { target: 'x', node_kind: 'app_server' });
    const cmds = be.fetchFn.mock.calls.filter((cc) => /\/commands$/.test(cc[0] as string));
    const secondId = JSON.parse((cmds[1]![1] as RequestInit).body as string).command_id;
    expect(secondId).not.toBe(firstId);
  });

  it('transport error keeps the intent so a retry reuses the command_id', async () => {
    let firstAttempt = true;
    const be = fakeBackend();
    const orig = be.fetchFn.getMockImplementation()!;
    be.fetchFn.mockImplementation((url: string, init?: RequestInit) => {
      if (/\/commands$/.test(url) && (init?.method ?? 'GET') === 'POST' && firstAttempt) {
        firstAttempt = false;
        throw new TypeError('network down');
      }
      return orig(url, init);
    });
    const c = makeController(be.fetchFn);
    await c.bootstrapSession('s');
    await c.runCommand('ADD:x', 'ADD_NODE', { target: 'x', node_kind: 'app_server' });
    expect(g().lastError?.code).toBe('DATABASE_UNAVAILABLE');
    await c.runCommand('ADD:x', 'ADD_NODE', { target: 'x', node_kind: 'app_server' });
    const cmds = be.fetchFn.mock.calls.filter((cc) => /\/commands$/.test(cc[0] as string));
    const id1 = JSON.parse((cmds[0]![1] as RequestInit).body as string).command_id;
    const id2 = JSON.parse((cmds[1]![1] as RequestInit).body as string).command_id;
    expect(id2).toBe(id1);
  });

  it('ignores concurrent clicks on the same key (pending dedupe)', async () => {
    const be = fakeBackend();
    const c = makeController(be.fetchFn);
    await c.bootstrapSession('s');
    const [r1, r2] = await Promise.all([
      c.runCommand('PAUSE:on', 'PAUSE', { paused: true }),
      c.runCommand('PAUSE:on', 'PAUSE', { paused: true }),
    ]);
    expect(r2).toBeNull();
    expect(r1?.status).toBe('APPLIED');
    expect(be.fetchFn.mock.calls.filter((cc) => /\/commands$/.test(cc[0] as string))).toHaveLength(1);
  });

  // --- load error mapping (PROG-1) ---
  it('SESSION_NOT_FOUND at summary → not_found (no socket, no board)', async () => {
    const be = fakeBackend();
    be.state.summaryCode = 'SESSION_NOT_FOUND';
    await makeController(be.fetchFn).bootstrapSession('s');
    expect(g().loadState).toBe('not_found');
    expect(g().snapshot).toBeNull();
    expect(useConnectionStore.getState().socketStatus).toBe('idle');
  });

  it('SESSION_NOT_FOUND at snapshot stage → not_found', async () => {
    const be = fakeBackend();
    be.state.snapshotCode = 'SESSION_NOT_FOUND';
    await makeController(be.fetchFn).bootstrapSession('s');
    expect(g().loadState).toBe('not_found');
  });

  it('DATABASE_UNAVAILABLE → recoverable_error (distinct from not_found)', async () => {
    const be = fakeBackend();
    be.state.summaryCode = 'DATABASE_UNAVAILABLE';
    await makeController(be.fetchFn).bootstrapSession('s');
    expect(g().loadState).toBe('recoverable_error');
  });

  it('SNAPSHOT_VERSION_UNSUPPORTED → fatal_error', async () => {
    const be = fakeBackend();
    be.state.snapshotCode = 'SNAPSHOT_VERSION_UNSUPPORTED';
    await makeController(be.fetchFn).bootstrapSession('s');
    expect(g().loadState).toBe('fatal_error');
  });

  it('session switch: a late response from session A never lands in session B (§5)', async () => {
    let releaseA: () => void = () => {};
    const summary = (sid: string, rev = 0) =>
      res(200, makeSummary({ session_id: sid, revision: rev }));
    const snapshot = (sid: string) =>
      res(200, { session_id: sid, revision: 0, simulation_state_version: 2, snapshot: makeSnapshot({ app_servers: {} }) });
    const fetchFn = vi.fn((url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET';
      if (/\/game-sessions\/A$/.test(url) && method === 'GET') {
        // Session A summary is held until we release it.
        return new Promise<Response>((resolve) => {
          releaseA = () => resolve(summary("A"));
        });
      }
      if (/\/game-sessions\/B$/.test(url) && method === 'GET') return Promise.resolve(summary('B'));
      if (/\/A\/snapshot$/.test(url)) return Promise.resolve(snapshot('A'));
      if (/\/B\/snapshot$/.test(url)) return Promise.resolve(snapshot('B'));
      if (/\/events/.test(url)) return Promise.resolve(res(200, { session_id: 'x', events: [] }));
      throw new Error(`no route ${method} ${url}`);
    });
    const c = makeController(fetchFn);
    const pA = c.bootstrapSession('A'); // blocks on A summary
    await c.bootstrapSession('B'); // supersedes A
    releaseA(); // A's summary resolves late
    await pA;
    expect(g().sessionId).toBe('B');
    expect(g().loadState).toBe('ready');
    expect(g().summary?.session_id).toBe('B'); // A's late summary discarded
  });

  it('route recovery: not_found then bootstrap a valid session resets and readies', async () => {
    const be = fakeBackend();
    const c = makeController(be.fetchFn);
    be.state.summaryCode = 'SESSION_NOT_FOUND';
    await c.bootstrapSession('s');
    expect(g().loadState).toBe('not_found');
    be.state.summaryCode = null;
    await c.bootstrapSession('s');
    expect(g().loadState).toBe('ready');
    expect(g().loadError).toBeNull();
  });
});

describe('stableStringify', () => {
  it('is key-order independent', () => {
    expect(stableStringify({ a: 1, b: 2 })).toBe(stableStringify({ b: 2, a: 1 }));
  });
});

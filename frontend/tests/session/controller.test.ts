import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GameSessionController, stableStringify } from '../../src/session/controller';
import { useGameSessionStore } from '../../src/state/gameSessionStore';
import { useConnectionStore } from '../../src/state/connectionStore';
import { makeSummary, makeSnapshot } from '../helpers/factories';
import { makeSocketFactory } from '../helpers/fakeSocket';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status });
}

function commandResponse(seq: number, revision: number) {
  return {
    command_id: 'ignored',
    sequence: seq,
    status: 'APPLIED',
    reason_code: null,
    session_revision: revision,
    current_tick: revision,
    events: [],
    state_summary: {},
  };
}

/** Route fetch by method+path suffix. */
function router(routes: Array<{ match: RegExp; method?: string; handler: (init: RequestInit) => Response | Promise<Response> }>) {
  return vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    for (const r of routes) {
      if (r.match.test(url) && (r.method ?? method) === method) {
        return Promise.resolve(r.handler(init ?? {}));
      }
    }
    throw new Error(`no route for ${method} ${url}`);
  });
}

function makeController(fetchFn: ReturnType<typeof vi.fn>) {
  const { factory } = makeSocketFactory();
  return new GameSessionController({ baseWsUrl: 'ws://h', fetch: fetchFn as never, createWebSocket: factory });
}

describe('GameSessionController.runCommand', () => {
  beforeEach(() => {
    useGameSessionStore.getState().reset();
    useConnectionStore.getState().reset();
    useGameSessionStore.setState({ sessionId: 's', revision: 1 });
  });

  it('sends expected_revision and updates state on success', async () => {
    const fetchFn = router([
      { match: /\/commands$/, method: 'POST', handler: () => jsonResponse(200, commandResponse(1, 2)) },
      { match: /\/game-sessions\/s$/, method: 'GET', handler: () => jsonResponse(200, makeSummary({ revision: 2 })) },
    ]);
    const controller = makeController(fetchFn);
    const res = await controller.runCommand('PAUSE:on', 'PAUSE', { paused: true });
    expect(res?.status).toBe('APPLIED');
    const body = JSON.parse(fetchFn.mock.calls[0]![1]!.body as string);
    expect(body.expected_revision).toBe(1);
    expect('sequence' in body).toBe(false);
    expect(useGameSessionStore.getState().revision).toBe(2);
  });

  it('recovers from REVISION_CONFLICT without auto-retry and drops the intent', async () => {
    const fetchFn = router([
      {
        match: /\/commands$/,
        method: 'POST',
        handler: () =>
          jsonResponse(409, {
            error: { code: 'REVISION_CONFLICT', message: 'stale', details: { server_revision: 5 }, request_id: 'r' },
          }),
      },
      { match: /\/game-sessions\/s$/, method: 'GET', handler: () => jsonResponse(200, makeSummary({ revision: 5 })) },
      { match: /\/snapshot$/, method: 'GET', handler: () => jsonResponse(200, { session_id: 's', revision: 5, simulation_state_version: 2, snapshot: makeSnapshot() }) },
    ]);
    const controller = makeController(fetchFn);
    const res = await controller.runCommand('ADD_NODE:x', 'ADD_NODE', { target: 'x', node_kind: 'app_server' });
    expect(res).toBeNull();
    expect(useGameSessionStore.getState().lastError?.code).toBe('REVISION_CONFLICT');
    expect(useGameSessionStore.getState().revision).toBe(5); // reconciled
    // A re-issue after conflict uses a NEW command_id (intent dropped).
    const firstId = JSON.parse(fetchFn.mock.calls[0]![1]!.body as string).command_id;
    await controller.runCommand('ADD_NODE:x', 'ADD_NODE', { target: 'x', node_kind: 'app_server' }).catch(() => null);
    const retryCall = fetchFn.mock.calls.find((c, i) => i > 0 && /\/commands$/.test(c[0] as string));
    if (retryCall) {
      expect(JSON.parse(retryCall[1]!.body as string).command_id).not.toBe(firstId);
    }
  });

  it('reuses the same command_id when retrying an identical intent after a transport error', async () => {
    let firstAttempt = true;
    const fetchFn = router([
      {
        match: /\/commands$/,
        method: 'POST',
        handler: () => {
          if (firstAttempt) {
            firstAttempt = false;
            throw new TypeError('network down');
          }
          return jsonResponse(200, commandResponse(1, 2));
        },
      },
      { match: /\/game-sessions\/s$/, method: 'GET', handler: () => jsonResponse(200, makeSummary({ revision: 2 })) },
    ]);
    const controller = makeController(fetchFn);
    await controller.runCommand('ADD:x', 'ADD_NODE', { target: 'x', node_kind: 'app_server' });
    expect(useGameSessionStore.getState().lastError?.code).toBe('DATABASE_UNAVAILABLE');
    await controller.runCommand('ADD:x', 'ADD_NODE', { target: 'x', node_kind: 'app_server' });
    const commandCalls = fetchFn.mock.calls.filter((c) => /\/commands$/.test(c[0] as string));
    const id1 = JSON.parse(commandCalls[0]![1]!.body as string).command_id;
    const id2 = JSON.parse(commandCalls[1]![1]!.body as string).command_id;
    expect(id2).toBe(id1);
  });

  it('ignores concurrent clicks on the same action key (pending dedupe)', async () => {
    const fetchFn = router([
      { match: /\/commands$/, method: 'POST', handler: () => jsonResponse(200, commandResponse(1, 2)) },
      { match: /\/game-sessions\/s$/, method: 'GET', handler: () => jsonResponse(200, makeSummary({ revision: 2 })) },
    ]);
    const controller = makeController(fetchFn);
    const p1 = controller.runCommand('PAUSE:on', 'PAUSE', { paused: true });
    const p2 = controller.runCommand('PAUSE:on', 'PAUSE', { paused: true });
    const [r1, r2] = await Promise.all([p1, p2]);
    expect(r2).toBeNull(); // second was in-flight -> ignored
    expect(r1?.status).toBe('APPLIED');
    const commandCalls = fetchFn.mock.calls.filter((c) => /\/commands$/.test(c[0] as string));
    expect(commandCalls).toHaveLength(1);
  });
});

describe('stableStringify', () => {
  it('is key-order independent', () => {
    expect(stableStringify({ a: 1, b: 2 })).toBe(stableStringify({ b: 2, a: 1 }));
  });
});

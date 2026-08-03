/**
 * Session bootstrap lifecycle / StrictMode socket-idempotency tests.
 *
 * Reproduces the React StrictMode mount→unmount→remount sequence at the controller
 * level (bootstrap → teardown → bootstrap) with a DEFERRED first response, and
 * asserts the invariant: at most ONE live (CONNECTING/OPEN) game socket, no stale
 * store writes, no stale reconnect. Separate from the AssetRuntime provider tests.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { GameSessionController } from '../../src/session/controller';
import { useGameSessionStore } from '../../src/state/gameSessionStore';
import { useConnectionStore } from '../../src/state/connectionStore';
import { makeSnapshot, makeSummary } from '../helpers/factories';
import { makeSocketFactory, type FakeWebSocket } from '../helpers/fakeSocket';

function res(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status });
}

interface Gate {
  promise: Promise<void>;
  release: () => void;
}
function gate(): Gate {
  let release!: () => void;
  const promise = new Promise<void>((r) => (release = r));
  return { promise, release };
}

/** Fake backend where the FIRST GET summary can be held open via `summaryGate`. */
function deferrableBackend(summaryGate?: Gate) {
  let summaryCalls = 0;
  const summaryBody = () => makeSummary({ revision: 0, current_tick: 0 });
  const snapshotBody = () => ({
    session_id: 's',
    revision: 0,
    simulation_state_version: 2,
    snapshot: makeSnapshot({ clock: { tick: 0, tick_ms: 1000, speed: 1, paused: false } }),
  });
  const fetchFn = (url: string, init?: RequestInit): Promise<Response> => {
    const method = init?.method ?? 'GET';
    if (/\/snapshot$/.test(url)) return Promise.resolve(res(200, snapshotBody()));
    if (/\/events/.test(url)) return Promise.resolve(res(200, { session_id: 's', events: [] }));
    if (/\/game-sessions\/[^/]+$/.test(url) && method === 'GET') {
      summaryCalls += 1;
      if (summaryCalls === 1 && summaryGate) {
        return summaryGate.promise.then(() => res(200, summaryBody()));
      }
      return Promise.resolve(res(200, summaryBody()));
    }
    throw new Error(`no route ${method} ${url}`);
  };
  return { fetchFn };
}

function liveSockets(instances: FakeWebSocket[]): FakeWebSocket[] {
  // CONNECTING(0) / OPEN(1) / CLOSING(2) are "not yet CLOSED(3)".
  return instances.filter((s) => s.readyState !== 3);
}

const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

beforeEach(() => {
  useGameSessionStore.getState().reset();
  useConnectionStore.getState().reset();
});
afterEach(() => {
  useGameSessionStore.getState().reset();
  useConnectionStore.getState().reset();
});

function makeController(fetchFn: (u: string, i?: RequestInit) => Promise<Response>) {
  const sockets = makeSocketFactory();
  const controller = new GameSessionController({
    baseWsUrl: 'ws://test',
    fetch: fetchFn as unknown as typeof fetch,
    createWebSocket: sockets.factory,
  });
  return { controller, sockets };
}

describe('StrictMode bootstrap socket idempotency', () => {
  it('leaves exactly one live socket after bootstrap → teardown → bootstrap (stale first)', async () => {
    const g = gate();
    const { fetchFn } = deferrableBackend(g);
    const { controller, sockets } = makeController(fetchFn);

    const p1 = controller.bootstrapSession('s'); // hangs at first getSummary
    controller.teardown(); // StrictMode cleanup
    const p2 = controller.bootstrapSession('s'); // remount: fast path → connects
    await p2;
    g.release(); // now let the first (stale) bootstrap resume
    await p1;
    await flush();

    expect(liveSockets(sockets.instances)).toHaveLength(1);
    // The stale bootstrap never created a socket.
    expect(sockets.instances).toHaveLength(1);
    expect(useGameSessionStore.getState().loadState).toBe('ready');
  });

  it('creates no socket when teardown happens before the initial load resolves', async () => {
    const g = gate();
    const { fetchFn } = deferrableBackend(g);
    const { controller, sockets } = makeController(fetchFn);

    const p1 = controller.bootstrapSession('s'); // hangs
    controller.teardown(); // torn down before summary resolves
    g.release();
    await p1;
    await flush();

    expect(sockets.instances).toHaveLength(0);
    expect(liveSockets(sockets.instances)).toHaveLength(0);
    expect(useGameSessionStore.getState().loadState).not.toBe('ready');
  });

  it('session A→B (A resolves late): only B has a live socket, A is ignored', async () => {
    const g = gate();
    const { fetchFn } = deferrableBackend(g);
    const { controller, sockets } = makeController(fetchFn);

    const pa = controller.bootstrapSession('A'); // hangs at summary
    const pb = controller.bootstrapSession('B'); // supersedes A
    await pb;
    g.release();
    await pa;
    await flush();

    const live = liveSockets(sockets.instances);
    expect(live).toHaveLength(1);
    expect(live[0]!.url).toContain('B');
    expect(live[0]!.url).not.toContain('/A?');
  });

  it("a superseded socket's late onclose does not disconnect the current socket", async () => {
    const { fetchFn } = deferrableBackend();
    const { controller, sockets } = makeController(fetchFn);

    await controller.bootstrapSession('s'); // socket A
    const socketA = sockets.instances[sockets.instances.length - 1]!;
    await controller.bootstrapSession('s'); // teardown closes A, opens socket B
    const socketB = sockets.instances[sockets.instances.length - 1]!;
    useConnectionStore.getState().setSocketStatus('connected');

    socketA.serverClose(); // stale close fires after replacement
    await flush();

    expect(socketB.readyState).not.toBe(3); // B still live
    expect(useConnectionStore.getState().socketStatus).not.toBe('disconnected');
  });

  it('repeated teardown is idempotent and never throws', async () => {
    const { fetchFn } = deferrableBackend();
    const { controller, sockets } = makeController(fetchFn);
    await controller.bootstrapSession('s');
    expect(() => {
      controller.teardown();
      controller.teardown();
      controller.teardown();
    }).not.toThrow();
    await flush();
    expect(liveSockets(sockets.instances)).toHaveLength(0);
  });
});

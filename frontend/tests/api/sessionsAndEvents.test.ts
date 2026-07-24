import { describe, expect, it, vi } from 'vitest';
import { HttpClient } from '../../src/api/client';
import { createSession, getSnapshot, getSummary } from '../../src/api/gameSessions';
import { drainEvents, listEvents, MAX_EVENT_LIMIT } from '../../src/api/events';
import { makeEvent } from '../helpers/factories';

function ok(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

describe('game session REST', () => {
  it('createSession only sends contract inputs', async () => {
    const fetchFn = vi.fn().mockResolvedValue(ok({ session_id: 's', revision: 0 }));
    const http = new HttpClient({ fetch: fetchFn });
    await createSession(http, { seed: 7, users: 50 });
    expect(JSON.parse((fetchFn.mock.calls[0]![1] as RequestInit).body as string)).toEqual({
      seed: 7,
      users: 50,
    });
  });

  it('getSummary and getSnapshot hit the right paths', async () => {
    const fetchFn = vi.fn().mockImplementation(() => Promise.resolve(ok({})));
    const http = new HttpClient({ fetch: fetchFn });
    await getSummary(http, 'abc');
    await getSnapshot(http, 'abc');
    expect(fetchFn.mock.calls[0]![0]).toBe('/api/v1/game-sessions/abc');
    expect(fetchFn.mock.calls[1]![0]).toBe('/api/v1/game-sessions/abc/snapshot');
  });
});

describe('events pagination', () => {
  it('uses exclusive after_cursor and caps limit at the contract max', async () => {
    const fetchFn = vi.fn().mockResolvedValue(ok({ session_id: 's', events: [] }));
    const http = new HttpClient({ fetch: fetchFn });
    await listEvents(http, 's', { afterCursor: 42, limit: 99999 });
    expect(fetchFn.mock.calls[0]![0]).toBe(
      `/api/v1/game-sessions/s/events?after_cursor=42&limit=${MAX_EVENT_LIMIT}`,
    );
  });

  it('drainEvents follows pages until a short page', async () => {
    const page1 = Array.from({ length: 100 }, (_, i) => makeEvent({ cursor: i + 1 }));
    const page2 = [makeEvent({ cursor: 101 })];
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce(ok({ session_id: 's', events: page1 }))
      .mockResolvedValueOnce(ok({ session_id: 's', events: page2 }));
    const http = new HttpClient({ fetch: fetchFn });
    const all = await drainEvents(http, 's', 0, 100);
    expect(all).toHaveLength(101);
    expect(fetchFn.mock.calls[1]![0]).toContain('after_cursor=100');
  });
});

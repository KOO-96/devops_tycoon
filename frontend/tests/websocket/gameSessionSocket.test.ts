import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GameSessionSocket } from '../../src/websocket/gameSessionSocket';
import type { EventEnvelope } from '../../src/api/schemas';
import { FakeWebSocket, makeSocketFactory, makeTimerQueue } from '../helpers/fakeSocket';
import { makeEvent, wsDomainEvent } from '../helpers/factories';

/** Non-optional accessor to satisfy noUncheckedIndexedAccess. */
function at(instances: FakeWebSocket[], i: number): FakeWebSocket {
  const ws = instances[i];
  if (!ws) throw new Error(`no socket instance at ${i}`);
  return ws;
}

function setup(initialCursor = 0) {
  const { factory, instances } = makeSocketFactory();
  const timers = makeTimerQueue();
  const received: EventEnvelope[] = [];
  const statuses: string[] = [];
  let protocolMismatch: number | null = null;
  const socket = new GameSessionSocket({
    baseWsUrl: 'ws://h',
    sessionId: 's',
    createWebSocket: factory,
    initialCursor,
    backoff: { baseMs: 10, random: () => 1, maxAttempts: 3 },
    setTimeoutFn: timers.setTimeoutFn,
    clearTimeoutFn: timers.clearTimeoutFn,
    handlers: {
      onDomainEvent: (e) => received.push(e),
      onStatusChange: (s) => statuses.push(s),
      onProtocolMismatch: (v) => (protocolMismatch = v),
    },
  });
  return { socket, instances, timers, received, statuses, getMismatch: () => protocolMismatch };
}

describe('GameSessionSocket', () => {
  beforeEach(() => vi.clearAllMocks());

  it('connects and transitions to connected on open', () => {
    const { socket, instances, statuses } = setup();
    socket.connect();
    expect(statuses).toContain('connecting');
    at(instances, 0).open();
    expect(socket.status).toBe('connected');
    expect(statuses).toContain('connected');
  });

  it('delivers replay + live events and advances the cursor', () => {
    const { socket, instances, received } = setup();
    socket.connect();
    at(instances, 0).open();
    const e1 = makeEvent({ cursor: 5, event_id: 'a' });
    const e2 = makeEvent({ cursor: 6, event_id: 'b' });
    at(instances, 0).emit(wsDomainEvent(e1));
    at(instances, 0).emit(wsDomainEvent(e2));
    expect(received.map((e) => e.event_id)).toEqual(['a', 'b']);
    expect(socket.cursor).toBe(6);
  });

  it('de-duplicates by event_id and ignores already-delivered cursors', () => {
    const { socket, instances, received } = setup();
    socket.connect();
    at(instances, 0).open();
    const e = makeEvent({ cursor: 5, event_id: 'a' });
    at(instances, 0).emit(wsDomainEvent(e));
    at(instances, 0).emit(wsDomainEvent(e)); // duplicate id
    at(instances, 0).emit(wsDomainEvent(makeEvent({ cursor: 4, event_id: 'old' }))); // stale cursor
    expect(received).toHaveLength(1);
  });

  it('reconnects using after_cursor = last processed cursor', () => {
    const { socket, instances, timers } = setup();
    socket.connect();
    at(instances, 0).open();
    at(instances, 0).emit(wsDomainEvent(makeEvent({ cursor: 9, event_id: 'x' })));
    at(instances, 0).serverClose();
    expect(socket.status).toBe('reconnecting');
    timers.flush();
    expect(instances).toHaveLength(2);
    expect(at(instances, 1).url).toContain('after_cursor=9');
  });

  it('gives up after max reconnect attempts -> failed', () => {
    const { socket, instances, timers } = setup();
    socket.connect();
    for (let i = 0; i < 3; i++) {
      at(instances, instances.length - 1).serverClose();
      timers.flush();
    }
    at(instances, instances.length - 1).serverClose();
    expect(socket.status).toBe('failed');
  });

  it('treats a protocol_version mismatch as fatal (no reconnect)', () => {
    const { socket, instances, timers, getMismatch } = setup();
    socket.connect();
    at(instances, 0).open();
    at(instances, 0).emitRaw(
      JSON.stringify({ protocol_version: 2, message_type: 'HEARTBEAT', session_id: 's', cursor: 0, payload: {} }),
    );
    expect(getMismatch()).toBe(2);
    expect(socket.status).toBe('failed');
    timers.flush();
    expect(instances).toHaveLength(1); // no reconnect attempt
  });

  it('ignores unknown message types', () => {
    const { socket, instances, received } = setup();
    socket.connect();
    at(instances, 0).open();
    at(instances, 0).emitRaw(
      JSON.stringify({ protocol_version: 1, message_type: 'FUTURE', session_id: 's', cursor: 0, payload: {} }),
    );
    expect(received).toHaveLength(0);
    expect(socket.status).toBe('connected');
  });

  it('client close does not schedule a reconnect and cleans up', () => {
    const { socket, instances, timers } = setup();
    socket.connect();
    at(instances, 0).open();
    socket.close();
    expect(socket.status).toBe('disconnected');
    expect(timers.size).toBe(0);
  });
});

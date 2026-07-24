import type { WebSocketLike } from '../../src/websocket/gameSessionSocket';

/** Controllable WebSocket double for deterministic socket tests. */
export class FakeWebSocket implements WebSocketLike {
  onopen: ((ev: unknown) => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: ((ev: { code?: number; reason?: string }) => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;
  readyState = 0;
  sent: string[] = [];
  closedByClient = false;

  constructor(public readonly url: string) {}

  open(): void {
    this.readyState = 1;
    this.onopen?.({});
  }

  emit(message: unknown): void {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  emitRaw(raw: string): void {
    this.onmessage?.({ data: raw });
  }

  /** Simulate a server-side / network close (triggers reconnect logic). */
  serverClose(): void {
    this.readyState = 3;
    this.onclose?.({});
  }

  close(): void {
    this.readyState = 3;
    this.closedByClient = true;
    this.onclose?.({});
  }

  send(data: string): void {
    this.sent.push(data);
  }
}

/** A factory that records every socket it creates. */
export function makeSocketFactory(): {
  factory: (url: string) => WebSocketLike;
  instances: FakeWebSocket[];
} {
  const instances: FakeWebSocket[] = [];
  return {
    instances,
    factory: (url: string) => {
      const ws = new FakeWebSocket(url);
      instances.push(ws);
      return ws;
    },
  };
}

/** Manual timer queue so reconnect delays are deterministic. */
export function makeTimerQueue() {
  const queue: Array<{ id: number; cb: () => void }> = [];
  let nextId = 1;
  return {
    setTimeoutFn: (cb: () => void, _ms: number): number => {
      const id = nextId++;
      queue.push({ id, cb });
      return id;
    },
    clearTimeoutFn: (id: number): void => {
      const i = queue.findIndex((t) => t.id === id);
      if (i >= 0) queue.splice(i, 1);
    },
    flush(): void {
      const pending = queue.splice(0, queue.length);
      for (const t of pending) t.cb();
    },
    get size(): number {
      return queue.length;
    },
  };
}

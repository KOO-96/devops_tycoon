/**
 * Game session WebSocket client (§14–17).
 *
 * Responsibilities:
 * - lifecycle state machine (idle → connecting → connected → reconnecting → …)
 * - de-duplicate DOMAIN_EVENTs by `event_id` and advance a cursor watermark
 * - reconnect with `after_cursor = last_processed_cursor` (at-least-once recovery)
 * - reject a `protocol_version` mismatch as a fatal connection error
 * - ignore unknown `message_type` (forward compatibility)
 *
 * A disconnect is NOT data loss: PostgreSQL is the source of truth and events are
 * recovered on reconnect / via the events REST endpoint (BACK-FU-007, §17).
 *
 * The WebSocket implementation and timers are injectable so this is fully
 * unit-testable without a browser or real sockets.
 */

import { BoundedSet } from '../utils/boundedSet';
import type { EventEnvelope } from '../api/schemas';
import { Backoff, type BackoffOptions } from './reconnect';
import {
  asEventEnvelope,
  buildSocketUrl,
  parseServerMessage,
  type ServerMessage,
} from './protocol';

export type SocketStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected'
  | 'failed';

export interface WebSocketLike {
  onopen: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: string }) => void) | null;
  onclose: ((ev: { code?: number; reason?: string }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  close(code?: number, reason?: string): void;
  send(data: string): void;
  readonly readyState: number;
}

export type WebSocketFactory = (url: string) => WebSocketLike;

export interface GameSessionSocketOptions {
  baseWsUrl: string;
  sessionId: string;
  createWebSocket: WebSocketFactory;
  initialCursor?: number;
  recentIdCapacity?: number;
  backoff?: BackoffOptions;
  setTimeoutFn?: (cb: () => void, ms: number) => number;
  clearTimeoutFn?: (handle: number) => void;
  handlers?: SocketHandlers;
}

export interface SocketHandlers {
  onStatusChange?: (status: SocketStatus) => void;
  onSessionState?: (payload: Record<string, unknown>) => void;
  onSnapshot?: (payload: Record<string, unknown>) => void;
  onDomainEvent?: (event: EventEnvelope) => void;
  onCommandResult?: (payload: Record<string, unknown>) => void;
  onError?: (payload: Record<string, unknown>) => void;
  onHeartbeat?: () => void;
  onProtocolMismatch?: (version: number) => void;
}

export class GameSessionSocket {
  private readonly opts: GameSessionSocketOptions;
  private readonly handlers: SocketHandlers;
  private readonly backoff: Backoff;
  private readonly recentEventIds: BoundedSet<string>;
  private readonly setTimeoutFn: (cb: () => void, ms: number) => number;
  private readonly clearTimeoutFn: (handle: number) => void;

  private socket: WebSocketLike | null = null;
  private _status: SocketStatus = 'idle';
  private lastProcessedCursor: number;
  private reconnectHandle: number | null = null;
  private closedByClient = false;

  constructor(options: GameSessionSocketOptions) {
    this.opts = options;
    this.handlers = options.handlers ?? {};
    this.backoff = new Backoff(options.backoff);
    this.recentEventIds = new BoundedSet<string>(options.recentIdCapacity ?? 4096);
    this.lastProcessedCursor = options.initialCursor ?? 0;
    // Browser timers: window.setTimeout returns a number (Node's returns Timeout).
    this.setTimeoutFn = options.setTimeoutFn ?? ((cb, ms) => window.setTimeout(cb, ms));
    this.clearTimeoutFn = options.clearTimeoutFn ?? ((h) => window.clearTimeout(h));
  }

  get status(): SocketStatus {
    return this._status;
  }

  get cursor(): number {
    return this.lastProcessedCursor;
  }

  /** Open the connection (or reopen after an explicit close). */
  connect(): void {
    this.closedByClient = false;
    this.openSocket('connecting');
  }

  /** Permanently close and release all resources (§26 cleanup). */
  close(): void {
    this.closedByClient = true;
    this.cancelReconnect();
    this.teardownSocket();
    this.setStatus('disconnected');
  }

  private openSocket(status: SocketStatus): void {
    this.setStatus(status);
    const url = buildSocketUrl(this.opts.baseWsUrl, this.opts.sessionId, this.lastProcessedCursor);
    let socket: WebSocketLike;
    try {
      socket = this.opts.createWebSocket(url);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;
    socket.onopen = () => {
      this.backoff.reset();
      this.setStatus('connected');
    };
    socket.onmessage = (ev) => this.handleRaw(ev.data);
    socket.onclose = () => this.handleClose();
    socket.onerror = () => {
      /* onclose follows; reconnect is scheduled there */
    };
  }

  private handleRaw(raw: string): void {
    const result = parseServerMessage(raw);
    switch (result.kind) {
      case 'protocol-mismatch':
        this.handlers.onProtocolMismatch?.(result.version);
        this.closedByClient = true; // fatal: do not reconnect
        this.teardownSocket();
        this.setStatus('failed');
        return;
      case 'unknown-type':
      case 'invalid':
        return; // forward-compatible / defensive: ignore
      case 'message':
        this.dispatch(result.message);
    }
  }

  private dispatch(message: ServerMessage): void {
    switch (message.message_type) {
      case 'SESSION_STATE':
        this.handlers.onSessionState?.(message.payload);
        return;
      case 'SESSION_SNAPSHOT':
        this.handlers.onSnapshot?.(message.payload);
        return;
      case 'COMMAND_RESULT':
        this.handlers.onCommandResult?.(message.payload);
        return;
      case 'HEARTBEAT':
        this.handlers.onHeartbeat?.();
        return;
      case 'ERROR':
        this.handlers.onError?.(message.payload);
        return;
      case 'DOMAIN_EVENT':
        this.handleDomainEvent(message);
    }
  }

  private handleDomainEvent(message: ServerMessage): void {
    const event = asEventEnvelope(message);
    if (event === null) return;
    // Primary dedupe: event_id. Secondary: cursor watermark (already-delivered).
    if (this.recentEventIds.has(event.event_id)) return;
    if (event.cursor <= this.lastProcessedCursor && this.lastProcessedCursor > 0) {
      this.recentEventIds.add(event.event_id);
      return;
    }
    this.recentEventIds.add(event.event_id);
    this.lastProcessedCursor = Math.max(this.lastProcessedCursor, event.cursor);
    this.handlers.onDomainEvent?.(event);
  }

  private handleClose(): void {
    this.socket = null;
    if (this.closedByClient) {
      this.setStatus('disconnected');
      return;
    }
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (this.backoff.exhausted) {
      this.setStatus('failed');
      return;
    }
    const delay = this.backoff.next();
    this.setStatus('reconnecting');
    this.reconnectHandle = this.setTimeoutFn(() => {
      this.reconnectHandle = null;
      if (this.closedByClient) return;
      this.openSocket('reconnecting');
    }, delay);
  }

  private cancelReconnect(): void {
    if (this.reconnectHandle !== null) {
      this.clearTimeoutFn(this.reconnectHandle);
      this.reconnectHandle = null;
    }
  }

  private teardownSocket(): void {
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = null;
      try {
        socket.close();
      } catch {
        /* already closing */
      }
    }
  }

  private setStatus(status: SocketStatus): void {
    if (this._status === status) return;
    this._status = status;
    this.handlers.onStatusChange?.(status);
  }
}

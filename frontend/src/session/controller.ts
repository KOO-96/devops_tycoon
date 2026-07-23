/**
 * Session controller: the single place that wires REST + WebSocket to the stores
 * and enforces the command/revision/idempotency policies (§11, §12, §22).
 *
 * Kept framework-free (no React) so it is unit-testable; React pages call it and
 * subscribe to the stores.
 */

import { HttpClient, type FetchLike } from '../api/client';
import { ApiError } from '../api/errors';
import { buildCommand, sendCommand } from '../api/commands';
import { createSession, getSnapshot, getSummary } from '../api/gameSessions';
import { drainEvents } from '../api/events';
import type { AnyCommandRequest, CommandPayloadMap, CommandType } from '../api/commandTypes';
import type { CommandResponse, CreateSessionRequest } from '../api/schemas';
import { useConnectionStore } from '../state/connectionStore';
import { useGameSessionStore } from '../state/gameSessionStore';
import {
  GameSessionSocket,
  type WebSocketFactory,
} from '../websocket/gameSessionSocket';

export interface ControllerConfig {
  baseUrl?: string;
  baseWsUrl: string;
  fetch?: FetchLike;
  createWebSocket: WebSocketFactory;
}

interface IntentRecord {
  commandId: string;
  payloadKey: string;
}

export class GameSessionController {
  private readonly http: HttpClient;
  private readonly config: ControllerConfig;
  private socket: GameSessionSocket | null = null;
  private readonly intents = new Map<string, IntentRecord>();

  constructor(config: ControllerConfig) {
    this.config = config;
    const opts: { baseUrl?: string; fetch?: FetchLike } = {};
    if (config.baseUrl !== undefined) opts.baseUrl = config.baseUrl;
    if (config.fetch !== undefined) opts.fetch = config.fetch;
    this.http = new HttpClient(opts);
  }

  private get game() {
    return useGameSessionStore.getState();
  }
  private get conn() {
    return useConnectionStore.getState();
  }

  /** Create a brand-new session and connect (§8). */
  async startNewGame(req: CreateSessionRequest = {}): Promise<string> {
    const res = await this.withBackend(() => createSession(this.http, req));
    this.game.reset();
    this.conn.reset();
    this.game.initFromCreate(res);
    await this.refreshSummary(res.session_id);
    this.connectSocket(res.session_id);
    return res.session_id;
  }

  /** Attach to an existing session after a reload/state loss (§15). */
  async resume(sessionId: string): Promise<void> {
    this.game.reset();
    this.conn.reset();
    const snapshot = await this.withBackend(() => getSnapshot(this.http, sessionId));
    this.game.setSnapshot(snapshot);
    useGameSessionStore.setState({ sessionId });
    await this.refreshSummary(sessionId);
    const events = await this.withBackend(() =>
      drainEvents(this.http, sessionId, this.game.lastProcessedCursor),
    );
    this.game.applyEvents(events);
    this.connectSocket(sessionId);
  }

  async refreshSummary(sessionId: string): Promise<void> {
    const summary = await this.withBackend(() => getSummary(this.http, sessionId));
    this.game.setSummary(summary);
  }

  async refreshSnapshot(sessionId: string): Promise<void> {
    const snapshot = await this.withBackend(() => getSnapshot(this.http, sessionId));
    this.game.setSnapshot(snapshot);
  }

  /**
   * Send a command for a UI action `key`. Concurrent clicks on the same key are
   * ignored while in flight (§22). A retry of the SAME intent (same key + same
   * payload) reuses the command_id; a changed payload gets a new one (§11).
   */
  async runCommand<T extends CommandType>(
    key: string,
    commandType: T,
    payload: CommandPayloadMap[T],
  ): Promise<CommandResponse | null> {
    const sessionId = this.game.sessionId;
    if (sessionId === null) return null;
    if (this.game.isPending(key)) return null; // dedupe rapid clicks

    const payloadKey = `${commandType}:${stableStringify(payload)}`;
    const prior = this.intents.get(key);
    const commandId =
      prior && prior.payloadKey === payloadKey ? prior.commandId : undefined;

    const request = buildCommand(commandType, payload, {
      expectedRevision: this.game.revision,
      ...(commandId !== undefined ? { commandId } : {}),
    });
    this.intents.set(key, { commandId: request.command_id, payloadKey });

    this.game.beginPending({
      key,
      commandId: request.command_id,
      commandType,
      payload: payload as Record<string, unknown>,
      status: 'in_flight',
    });

    try {
      // `request` is a CommandRequest<T>, i.e. one member of the union.
      const res = await sendCommand(this.http, sessionId, request as AnyCommandRequest);
      this.game.setSummary(await getSummary(this.http, sessionId));
      this.game.applyEvents(res.events);
      useGameSessionStore.setState((s) => ({ revision: Math.max(s.revision, res.session_revision) }));
      this.game.setError(null);
      this.intents.delete(key); // intent completed
      return res;
    } catch (err) {
      await this.handleCommandError(sessionId, key, err);
      return null;
    } finally {
      this.game.clearPending(key);
    }
  }

  private async handleCommandError(sessionId: string, key: string, err: unknown): Promise<void> {
    if (!(err instanceof ApiError)) {
      this.game.setError({ code: 'INTERNAL_ERROR', message: 'Unexpected error.', requestId: '' });
      return;
    }
    this.game.setError({ code: err.code, message: err.message, requestId: err.requestId });

    if (err.code === 'REVISION_CONFLICT') {
      // Stop; reconcile to the server state. A re-issue must use a new command_id,
      // so drop the remembered intent (§12).
      this.intents.delete(key);
      await this.refreshSummary(sessionId).catch(() => undefined);
      await this.refreshSnapshot(sessionId).catch(() => undefined);
      return;
    }
    if (err.code === 'IDEMPOTENCY_CONFLICT') {
      // Never auto-mutate payload and resend; surface to the user.
      this.intents.delete(key);
      return;
    }
    // Transport/5xx: keep the intent so a manual retry reuses the same command_id.
    if (err.code === 'DATABASE_UNAVAILABLE') {
      this.conn.setBackendStatus('unreachable');
    }
  }

  private connectSocket(sessionId: string): void {
    this.socket?.close();
    const socket = new GameSessionSocket({
      baseWsUrl: this.config.baseWsUrl,
      sessionId,
      createWebSocket: this.config.createWebSocket,
      initialCursor: this.game.lastProcessedCursor,
      handlers: {
        onStatusChange: (status) => this.conn.setSocketStatus(status),
        onSessionState: (payload) => this.game.setSummary(payload as never),
        onDomainEvent: (event) => {
          this.game.applyEvent(event);
        },
        onError: (payload) => {
          const code = typeof payload['code'] === 'string' ? payload['code'] : 'INTERNAL_ERROR';
          const message =
            typeof payload['message'] === 'string' ? payload['message'] : 'Socket error.';
          this.game.setError({ code: code as never, message, requestId: '' });
        },
        onProtocolMismatch: (version) => {
          this.conn.setProtocolError(`Unsupported protocol_version ${version}`);
        },
      },
    });
    this.socket = socket;
    socket.connect();
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = null;
  }

  private async withBackend<T>(fn: () => Promise<T>): Promise<T> {
    try {
      const result = await fn();
      this.conn.setBackendStatus('ok');
      return result;
    } catch (err) {
      if (err instanceof ApiError && err.code === 'DATABASE_UNAVAILABLE') {
        this.conn.setBackendStatus('unreachable');
      }
      throw err;
    }
  }
}

/** Stable stringify so `{a:1,b:2}` and `{b:2,a:1}` produce the same intent key. */
export function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  const entries = Object.entries(value as Record<string, unknown>).sort(([a], [b]) =>
    a < b ? -1 : a > b ? 1 : 0,
  );
  return `{${entries.map(([k, v]) => `${JSON.stringify(k)}:${stableStringify(v)}`).join(',')}}`;
}

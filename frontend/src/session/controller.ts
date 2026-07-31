/**
 * Session controller: the single place that wires REST + WebSocket to the stores
 * and enforces the bootstrap / command / revision / idempotency policies
 * (§2–§12, §22).
 *
 * Kept framework-free (no React) so it is unit-testable; React pages call it and
 * subscribe to the stores.
 *
 * A monotonic lifecycle `generation` token guards every async result: a late reply
 * from a previous session or a superseded bootstrap is discarded and never written
 * to the store, and — critically — never opens a socket (§5). `teardown()` BUMPS the
 * generation and aborts the in-flight bootstrap, so a React StrictMode
 * mount→unmount→remount (which fires bootstrap → teardown → bootstrap) can never
 * leave two live sockets: the first bootstrap is invalidated before it connects, and
 * if it already connected, teardown closed it. All entry paths — new game, direct
 * URL, reload, session switch, retry — go through the single `bootstrapSession` flow.
 */

import { HttpClient, type FetchLike } from '../api/client';
import { ApiError, type ErrorCode } from '../api/errors';
import { buildCommand, sendCommand } from '../api/commands';
import { createSession, getSnapshot, getSummary } from '../api/gameSessions';
import { drainEvents } from '../api/events';
import type { AnyCommandRequest, CommandPayloadMap, CommandType } from '../api/commandTypes';
import type { CommandResponse, CreateSessionRequest } from '../api/schemas';
import { useConnectionStore } from '../state/connectionStore';
import { useGameSessionStore, type UiError } from '../state/gameSessionStore';
import { GameSessionSocket, type WebSocketFactory } from '../websocket/gameSessionSocket';

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

const SUMMARY_POLL_MS = 3000;

export class GameSessionController {
  private readonly http: HttpClient;
  private readonly config: ControllerConfig;
  private socket: GameSessionSocket | null = null;
  private pollTimer: number | null = null;
  private generation = 0;
  private bootstrapAbort: AbortController | null = null;
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

  /** Create a brand-new session and return its id (§8). The board is loaded by
   * the GamePage bootstrap, so new-game / direct-URL / reload share one path. */
  async startNewGame(req: CreateSessionRequest = {}): Promise<string> {
    const res = await this.withBackend(() => createSession(this.http, req));
    return res.session_id;
  }

  /**
   * The single session bootstrap flow (§2/§3.1). Used for new game, direct URL,
   * reload, session switch, and retry. Cleans up any prior session, loads
   * summary + snapshot + event replay, connects the socket, and starts polling.
   */
  async bootstrapSession(sessionId: string): Promise<void> {
    this.teardown(); // stop prior socket / polling AND bump generation + abort (§4)
    const gen = this.generation; // this bootstrap owns the post-teardown generation
    const abort = new AbortController();
    this.bootstrapAbort = abort;
    this.game.beginLoad(sessionId, gen); // full store reset + loading state (§4)
    this.conn.reset();
    try {
      const summary = await this.withBackend(() => getSummary(this.http, sessionId));
      if (!this.isCurrent(sessionId, gen, abort.signal)) return;
      const snapshot = await this.withBackend(() => getSnapshot(this.http, sessionId));
      if (!this.isCurrent(sessionId, gen, abort.signal)) return;
      // Snapshot is the source of truth for the board; summary is the HUD projection.
      this.game.setSnapshot(snapshot);
      this.game.setSummary(summary);
      const events = await this.withBackend(() =>
        drainEvents(this.http, sessionId, this.game.lastProcessedCursor),
      );
      if (!this.isCurrent(sessionId, gen, abort.signal)) return;
      this.game.applyEvents(events);
      this.connectSocket(sessionId, gen); // guarded: a stale generation opens no socket
      if (!this.isCurrent(sessionId, gen, abort.signal)) return;
      this.game.setLoadState('ready');
      this.startPolling(sessionId, gen);
    } catch (err) {
      if (!this.isCurrent(sessionId, gen, abort.signal)) return;
      this.mapLoadError(err);
    }
  }

  /** Re-run the bootstrap for the active session (recoverable-error retry, §11). */
  async retry(): Promise<void> {
    const sessionId = this.game.sessionId;
    if (sessionId !== null) await this.bootstrapSession(sessionId);
  }

  /** Re-fetch snapshot+summary after a failed post-command sync (§7). Never
   * re-sends the command. */
  async retrySnapshotSync(): Promise<void> {
    const sessionId = this.game.sessionId;
    if (sessionId !== null) await this.syncAfterCommand(sessionId, this.generation);
  }

  async refreshSummary(sessionId: string): Promise<void> {
    const gen = this.generation;
    const summary = await this.withBackend(() => getSummary(this.http, sessionId));
    if (!this.isCurrent(sessionId, gen)) return;
    this.game.setSummary(summary);
  }

  async refreshSnapshot(sessionId: string): Promise<void> {
    const gen = this.generation;
    const snapshot = await this.withBackend(() => getSnapshot(this.http, sessionId));
    if (!this.isCurrent(sessionId, gen)) return;
    this.game.setSnapshot(snapshot);
  }

  /**
   * Send a command for a UI action `key`. Concurrent clicks on the same key are
   * ignored while in flight (§22). A retry of the SAME intent (same key + same
   * payload) reuses the command_id; a changed payload gets a new one (§11). After
   * a successful state-changing command the snapshot is re-fetched so the board
   * reflects backend state without a reload (§6).
   */
  async runCommand<T extends CommandType>(
    key: string,
    commandType: T,
    payload: CommandPayloadMap[T],
  ): Promise<CommandResponse | null> {
    const sessionId = this.game.sessionId;
    if (sessionId === null) return null;
    if (this.game.isPending(key)) return null; // dedupe rapid clicks
    const gen = this.generation;

    const payloadKey = `${commandType}:${stableStringify(payload)}`;
    const prior = this.intents.get(key);
    const commandId = prior && prior.payloadKey === payloadKey ? prior.commandId : undefined;

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
      if (!this.isCurrent(sessionId, gen)) {
        this.intents.delete(key);
        return res; // session switched mid-flight: do not write stale state
      }
      this.game.applyEvents(res.events);
      useGameSessionStore.setState((s) => ({
        revision: Math.max(s.revision, res.session_revision),
      }));
      this.intents.delete(key); // intent completed
      if (res.status === 'APPLIED' || res.status === 'ALREADY_APPLIED') {
        // Re-fetch the snapshot so board/NodeList/HUD reflect the change (§6).
        await this.syncAfterCommand(sessionId, gen);
      } else {
        // No state change (e.g. COMMAND_REJECTED): keep the snapshot, refresh HUD.
        await this.refreshSummary(sessionId).catch(() => undefined);
      }
      return res;
    } catch (err) {
      await this.handleCommandError(sessionId, key, err);
      return null;
    } finally {
      this.game.clearPending(key);
    }
  }

  /** Re-fetch snapshot + summary after a command; on failure mark the view
   * out-of-sync without re-running the command (§7). */
  private async syncAfterCommand(sessionId: string, gen: number): Promise<void> {
    this.game.setSnapshotSyncState('syncing');
    try {
      const snapshot = await getSnapshot(this.http, sessionId);
      const summary = await getSummary(this.http, sessionId);
      if (!this.isCurrent(sessionId, gen)) return;
      this.game.setSnapshot(snapshot);
      this.game.setSummary(summary);
      this.game.setSnapshotSyncState('synced');
      this.game.setError(null);
    } catch {
      if (!this.isCurrent(sessionId, gen)) return;
      // Command is committed on the backend; surface an out-of-sync state via the
      // dedicated SnapshotSyncBanner (with a Refresh action) rather than a generic
      // error. Never re-run the command / mint a new command_id (§7).
      this.game.setSnapshotSyncState('failed');
    }
  }

  private async handleCommandError(sessionId: string, key: string, err: unknown): Promise<void> {
    if (!(err instanceof ApiError)) {
      this.game.setError({ code: 'INTERNAL_ERROR', message: 'Unexpected error.', requestId: '' });
      return;
    }
    this.game.setError({ code: err.code, message: err.message, requestId: err.requestId });

    if (err.code === 'REVISION_CONFLICT') {
      // Stop; reconcile to server state. A re-issue must use a new command_id, so
      // drop the remembered intent (§12).
      this.intents.delete(key);
      await this.refreshSummary(sessionId).catch(() => undefined);
      await this.refreshSnapshot(sessionId).catch(() => undefined);
      return;
    }
    if (err.code === 'IDEMPOTENCY_CONFLICT') {
      this.intents.delete(key); // never auto-mutate payload and resend
      return;
    }
    // Transport/5xx: keep the intent so a manual retry reuses the same command_id.
    if (err.code === 'DATABASE_UNAVAILABLE') {
      this.conn.setBackendStatus('unreachable');
    }
  }

  private connectSocket(sessionId: string, gen: number): void {
    // A superseded bootstrap (StrictMode remount / session switch) must NOT open a
    // socket. Re-check the generation right before creating the socket.
    if (!this.isCurrent(sessionId, gen)) return;
    this.socket?.close();
    // `live` gates every handler on BOTH the generation and the socket identity, so a
    // stale socket's late event can never write to the store or null a newer socket.
    const isLive = (): boolean => this.generation === gen && this.socket === socket;
    const socket = new GameSessionSocket({
      baseWsUrl: this.config.baseWsUrl,
      sessionId,
      createWebSocket: this.config.createWebSocket,
      initialCursor: this.game.lastProcessedCursor,
      handlers: {
        onStatusChange: (status) => {
          if (isLive()) this.conn.setSocketStatus(status);
        },
        onSessionState: (payload) => {
          if (isLive()) this.game.setSummary(payload as never);
        },
        onDomainEvent: (event) => {
          if (isLive()) this.game.applyEvent(event);
        },
        onError: (payload) => {
          if (!isLive()) return;
          const code = typeof payload['code'] === 'string' ? payload['code'] : 'INTERNAL_ERROR';
          const message =
            typeof payload['message'] === 'string' ? payload['message'] : 'Socket error.';
          this.game.setError({ code: code as ErrorCode, message, requestId: '' });
        },
        onProtocolMismatch: (version) => {
          if (isLive()) this.conn.setProtocolError(`Unsupported protocol_version ${version}`);
        },
      },
    });
    this.socket = socket;
    socket.connect();
  }

  private startPolling(sessionId: string, gen: number): void {
    if (this.pollTimer !== null) window.clearInterval(this.pollTimer);
    this.pollTimer = window.setInterval(() => {
      if (!this.isCurrent(sessionId, gen)) return;
      void this.refreshSummary(sessionId).catch(() => undefined);
    }, SUMMARY_POLL_MS);
  }

  /** Stop all side effects (socket + polling) and INVALIDATE any in-flight bootstrap.
   * Bumping the generation + aborting means a superseded bootstrap resolving later
   * discards its result and opens no socket (§4). Idempotent: safe to call repeatedly;
   * a no-op teardown still advances the generation, which harmlessly invalidates any
   * pending async work. Store cleanup is done by beginLoad on the next bootstrap. */
  teardown(): void {
    this.generation += 1;
    this.bootstrapAbort?.abort();
    this.bootstrapAbort = null;
    this.socket?.close();
    this.socket = null;
    if (this.pollTimer !== null) {
      window.clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  /** Alias kept for GamePage unmount. */
  disconnect(): void {
    this.teardown();
  }

  private mapLoadError(err: unknown): void {
    this.teardown();
    if (err instanceof ApiError) {
      const ui: UiError = { code: err.code, message: err.message, requestId: err.requestId };
      if (err.code === 'SESSION_NOT_FOUND') {
        this.game.setLoadState('not_found', ui);
      } else if (err.code === 'DATABASE_UNAVAILABLE' || err.code === 'EVENT_BROKER_UNAVAILABLE') {
        this.game.setLoadState('recoverable_error', ui);
      } else {
        // SNAPSHOT_VERSION_UNSUPPORTED and any other unexpected code are fatal.
        this.game.setLoadState('fatal_error', ui);
      }
      return;
    }
    this.game.setLoadState('fatal_error', {
      code: 'INTERNAL_ERROR',
      message: 'Unexpected error while loading the session.',
      requestId: '',
    });
  }

  private isCurrent(sessionId: string, gen: number, signal?: AbortSignal): boolean {
    if (signal?.aborted === true) return false;
    return this.generation === gen && this.game.sessionId === sessionId;
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

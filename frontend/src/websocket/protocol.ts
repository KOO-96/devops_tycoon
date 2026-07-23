/**
 * WebSocket message protocol (§14). Mirrors `contracts/websocket/game-session-v1.md`.
 * `cursor` is always an integer; it is only meaningful for DOMAIN_EVENT (0 for
 * other types). Clients MUST ignore unknown `message_type` and reject a mismatched
 * `protocol_version`.
 */

import type { EventEnvelope } from '../api/schemas';

export const PROTOCOL_VERSION = 1;

export const MESSAGE_TYPES = [
  'SESSION_SNAPSHOT',
  'SESSION_STATE',
  'DOMAIN_EVENT',
  'COMMAND_RESULT',
  'ERROR',
  'HEARTBEAT',
] as const;

export type MessageType = (typeof MESSAGE_TYPES)[number];

const TYPE_SET = new Set<string>(MESSAGE_TYPES);

export interface ServerMessage {
  protocol_version: number;
  message_type: MessageType;
  session_id: string;
  cursor: number;
  payload: Record<string, unknown>;
}

export type ParseResult =
  | { kind: 'message'; message: ServerMessage }
  | { kind: 'unknown-type'; messageType: string }
  | { kind: 'protocol-mismatch'; version: number }
  | { kind: 'invalid' };

/**
 * Parse and classify a raw socket frame. Distinguishes an *unknown message_type*
 * (ignore, forward-compatible) from a *protocol_version mismatch* (fatal — the
 * caller must move to a connection-error state, §14) and from malformed frames.
 */
export function parseServerMessage(raw: string): ParseResult {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return { kind: 'invalid' };
  }
  if (typeof data !== 'object' || data === null) return { kind: 'invalid' };
  const obj = data as Record<string, unknown>;

  const version = obj['protocol_version'];
  if (typeof version !== 'number') return { kind: 'invalid' };
  if (version !== PROTOCOL_VERSION) return { kind: 'protocol-mismatch', version };

  const messageType = obj['message_type'];
  if (typeof messageType !== 'string') return { kind: 'invalid' };
  if (!TYPE_SET.has(messageType)) return { kind: 'unknown-type', messageType };

  const sessionId = obj['session_id'];
  const cursor = obj['cursor'];
  const payload = obj['payload'];
  if (typeof sessionId !== 'string' || typeof cursor !== 'number') return { kind: 'invalid' };

  return {
    kind: 'message',
    message: {
      protocol_version: version,
      message_type: messageType as MessageType,
      session_id: sessionId,
      cursor,
      payload: (typeof payload === 'object' && payload !== null
        ? (payload as Record<string, unknown>)
        : {}),
    },
  };
}

/** Interpret a DOMAIN_EVENT payload as an event envelope (best-effort typing). */
export function asEventEnvelope(message: ServerMessage): EventEnvelope | null {
  const p = message.payload;
  if (typeof p['event_id'] !== 'string' || typeof p['cursor'] !== 'number') return null;
  return p as unknown as EventEnvelope;
}

export function buildSocketUrl(baseWsUrl: string, sessionId: string, afterCursor: number): string {
  const sep = baseWsUrl.endsWith('/') ? '' : '/';
  return `${baseWsUrl}${sep}ws/v1/game-sessions/${encodeURIComponent(sessionId)}?after_cursor=${afterCursor}`;
}

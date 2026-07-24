import { describe, expect, it } from 'vitest';
import { asEventEnvelope, buildSocketUrl, parseServerMessage } from '../../src/websocket/protocol';
import { makeEvent, wsDomainEvent } from '../helpers/factories';

describe('parseServerMessage', () => {
  it('parses a valid DOMAIN_EVENT message', () => {
    const event = makeEvent();
    const result = parseServerMessage(JSON.stringify(wsDomainEvent(event)));
    expect(result.kind).toBe('message');
    if (result.kind === 'message') {
      expect(result.message.message_type).toBe('DOMAIN_EVENT');
      expect(asEventEnvelope(result.message)?.event_id).toBe(event.event_id);
    }
  });

  it('classifies an unknown message_type as forward-compatible (ignore)', () => {
    const raw = JSON.stringify({ protocol_version: 1, message_type: 'FUTURE', session_id: 's', cursor: 0, payload: {} });
    expect(parseServerMessage(raw)).toEqual({ kind: 'unknown-type', messageType: 'FUTURE' });
  });

  it('flags a protocol_version mismatch as fatal', () => {
    const raw = JSON.stringify({ protocol_version: 2, message_type: 'HEARTBEAT', session_id: 's', cursor: 0, payload: {} });
    expect(parseServerMessage(raw)).toEqual({ kind: 'protocol-mismatch', version: 2 });
  });

  it('rejects malformed frames', () => {
    expect(parseServerMessage('not json').kind).toBe('invalid');
    expect(parseServerMessage(JSON.stringify({ message_type: 'HEARTBEAT' })).kind).toBe('invalid');
  });
});

describe('buildSocketUrl', () => {
  it('encodes session id and after_cursor', () => {
    expect(buildSocketUrl('ws://h', 'a b', 5)).toBe('ws://h/ws/v1/game-sessions/a%20b?after_cursor=5');
  });
});

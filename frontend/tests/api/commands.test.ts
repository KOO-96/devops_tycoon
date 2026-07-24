import { describe, expect, it, vi } from 'vitest';
import { HttpClient } from '../../src/api/client';
import { buildCommand, sendCommand } from '../../src/api/commands';

describe('buildCommand', () => {
  it('builds a typed request with a fresh command_id and no sequence', () => {
    const cmd = buildCommand('ADD_NODE', { target: 'lb', node_kind: 'load_balancer' });
    expect(cmd.command_type).toBe('ADD_NODE');
    expect(cmd.command_id).toBeTruthy();
    expect('sequence' in cmd).toBe(false);
    expect(cmd.payload).toEqual({ target: 'lb', node_kind: 'load_balancer' });
  });

  it('includes expected_revision only when provided', () => {
    const withRev = buildCommand('PAUSE', { paused: true }, { expectedRevision: 3 });
    expect(withRev.expected_revision).toBe(3);
    const without = buildCommand('PAUSE', { paused: true });
    expect('expected_revision' in without).toBe(false);
  });

  it('reuses an explicit command_id for an identical retry', () => {
    const first = buildCommand('SET_SPEED', { speed: 2 });
    const retry = buildCommand('SET_SPEED', { speed: 2 }, { commandId: first.command_id });
    expect(retry.command_id).toBe(first.command_id);
  });

  it('generates distinct ids for distinct intents', () => {
    const a = buildCommand('SET_SPEED', { speed: 2 });
    const b = buildCommand('SET_SPEED', { speed: 4 });
    expect(a.command_id).not.toBe(b.command_id);
  });
});

describe('sendCommand', () => {
  it('POSTs to the session command path', async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ command_id: 'c', sequence: 1, status: 'APPLIED' }), {
        status: 200,
      }),
    );
    const http = new HttpClient({ fetch: fetchFn });
    await sendCommand(http, 'sess-1', buildCommand('PAUSE', { paused: true }));
    expect(fetchFn.mock.calls[0]![0]).toBe('/api/v1/game-sessions/sess-1/commands');
  });
});

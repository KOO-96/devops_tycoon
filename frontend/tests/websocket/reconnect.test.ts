import { describe, expect, it } from 'vitest';
import { Backoff } from '../../src/websocket/reconnect';

describe('Backoff', () => {
  it('grows exponentially and is bounded by maxMs', () => {
    const b = new Backoff({ baseMs: 100, factor: 2, maxMs: 800, random: () => 1 });
    expect(b.next()).toBe(100); // exp=100, jitter=full -> 100
    expect(b.next()).toBe(200);
    expect(b.next()).toBe(400);
    expect(b.next()).toBe(800);
    expect(b.next()).toBe(800); // capped
  });

  it('applies full jitter (lower half at random=0)', () => {
    const b = new Backoff({ baseMs: 100, factor: 2, maxMs: 800, random: () => 0 });
    expect(b.next()).toBe(50);
  });

  it('reports exhaustion after maxAttempts and resets', () => {
    const b = new Backoff({ maxAttempts: 2, random: () => 0 });
    b.next();
    b.next();
    expect(b.exhausted).toBe(true);
    b.reset();
    expect(b.exhausted).toBe(false);
    expect(b.attempts).toBe(0);
  });
});

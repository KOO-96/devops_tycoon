import { describe, expect, it, vi } from 'vitest';

vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));

import { runWithRetry, type SleepFn } from '../../src/game/pixi/assets/retry';
import { AssetLoadError } from '../../src/game/pixi/assets/assetLoader';

// A sleep where the long per-attempt timeout (>=1000ms) never resolves (so the
// attempt itself wins the race) and short backoff sleeps resolve immediately.
const backoffOnly: SleepFn = (ms) =>
  ms >= 1000 ? new Promise<void>(() => {}) : Promise.resolve();

// A sleep where EVERYTHING resolves immediately — used to fire attempt timeouts.
const fireTimeouts: SleepFn = () => Promise.resolve();

const retryable = (): AssetLoadError => new AssetLoadError('network', 'boom');
const nonRetryable = (): AssetLoadError => new AssetLoadError('client', '4xx');

describe('runWithRetry state machine', () => {
  it('returns on first success (1 attempt)', async () => {
    const attempt = vi.fn().mockResolvedValue('ok');
    const out = await runWithRetry({ sleep: backoffOnly, attempt });
    expect(out).toBe('ok');
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it('retries once then succeeds (2 attempts, 250ms backoff)', async () => {
    const attempt = vi
      .fn()
      .mockRejectedValueOnce(retryable())
      .mockResolvedValue('ok');
    const delays: number[] = [];
    const onRetry = (i: { delayMs: number }): void => {
      delays.push(i.delayMs);
    };
    const out = await runWithRetry({ sleep: backoffOnly, attempt, onRetry });
    expect(out).toBe('ok');
    expect(attempt).toHaveBeenCalledTimes(2);
    expect(delays).toEqual([250]);
  });

  it('retries twice then succeeds (3 attempts, 250 then 750ms)', async () => {
    const attempt = vi
      .fn()
      .mockRejectedValueOnce(retryable())
      .mockRejectedValueOnce(retryable())
      .mockResolvedValue('ok');
    const delays: number[] = [];
    const out = await runWithRetry({
      sleep: backoffOnly,
      attempt,
      onRetry: (i) => delays.push(i.delayMs),
    });
    expect(out).toBe('ok');
    expect(attempt).toHaveBeenCalledTimes(3);
    expect(delays).toEqual([250, 750]);
  });

  it('gives up after max retries (total 3 attempts)', async () => {
    const attempt = vi.fn().mockRejectedValue(retryable());
    await expect(runWithRetry({ sleep: backoffOnly, attempt })).rejects.toThrow();
    expect(attempt).toHaveBeenCalledTimes(3);
  });

  it('does NOT retry a non-retryable (4xx) error', async () => {
    const attempt = vi.fn().mockRejectedValue(nonRetryable());
    await expect(runWithRetry({ sleep: backoffOnly, attempt })).rejects.toThrow();
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it('times out an attempt and classifies timeout as retryable', async () => {
    // Attempt never resolves; the (immediate) timeout sleep fires each attempt.
    const attempt = vi.fn().mockImplementation(() => new Promise<never>(() => {}));
    await expect(
      runWithRetry({ sleep: fireTimeouts, attempt, policy: { attemptTimeoutMs: 10 } }),
    ).rejects.toBeInstanceOf(AssetLoadError);
    // 1 initial + 2 retries because timeout is retryable.
    expect(attempt).toHaveBeenCalledTimes(3);
  });

  it('does not start when the outer signal is already aborted', async () => {
    const ac = new AbortController();
    ac.abort();
    const attempt = vi.fn().mockResolvedValue('ok');
    await expect(
      runWithRetry({ sleep: backoffOnly, attempt, signal: ac.signal }),
    ).rejects.toBeInstanceOf(AssetLoadError);
    expect(attempt).not.toHaveBeenCalled();
  });

  it('stops retrying once the outer signal aborts', async () => {
    const ac = new AbortController();
    const attempt = vi.fn().mockImplementation(() => {
      ac.abort();
      return Promise.reject(retryable());
    });
    await expect(
      runWithRetry({ sleep: backoffOnly, attempt, signal: ac.signal }),
    ).rejects.toBeInstanceOf(AssetLoadError);
    expect(attempt).toHaveBeenCalledTimes(1);
  });
});

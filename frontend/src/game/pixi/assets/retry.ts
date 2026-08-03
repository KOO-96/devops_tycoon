/**
 * Asset retry state machine (POLICY-C-FU-004). Exact policy:
 *   - initial attempt: 1
 *   - automatic retries: max 2   → total attempts: max 3
 *   - per-attempt timeout: 8000ms
 *   - backoff before retry #1: 250ms, before retry #2: 750ms
 * Only retryable errors (network / transient 5xx / timeout) retry; 4xx / schema /
 * manifest / license / decode / not-found do NOT. Abort stops everything.
 *
 * Pure and injectable: `sleep` and the abort signal are parameters so tests use a
 * fake clock and never wait real seconds. No unhandled rejections.
 */

import { AssetLoadError, isRetryableError } from './assetLoader';

export interface RetryPolicy {
  maxRetries: number;
  attemptTimeoutMs: number;
  backoffMs: readonly number[];
}

export const DEFAULT_RETRY_POLICY: RetryPolicy = {
  maxRetries: 2,
  attemptTimeoutMs: 8000,
  backoffMs: [250, 750],
};

export interface AttemptContext {
  attempt: number; // 1-based
  signal: AbortSignal;
}

export type SleepFn = (ms: number, signal?: AbortSignal) => Promise<void>;

export interface RetryOptions<T> {
  policy?: Partial<RetryPolicy>;
  /** Outer abort (manager dispose / route leave). */
  signal?: AbortSignal;
  sleep?: SleepFn;
  isRetryable?: (err: unknown) => boolean;
  onRetry?: (info: { attempt: number; error: unknown; delayMs: number }) => void;
  onTimeout?: (attempt: number) => void;
  attempt: (ctx: AttemptContext) => Promise<T>;
}

/** Default sleep that RESOLVES on abort (clears its timer) so a raced timeout can
 * never leak an unhandled rejection. */
export const defaultSleep: SleepFn = (ms, signal) =>
  new Promise<void>((resolve) => {
    if (signal?.aborted) {
      resolve();
      return;
    }
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(t);
        resolve();
      },
      { once: true },
    );
  });

function abortError(reason: unknown): AssetLoadError {
  if (reason instanceof AssetLoadError) return reason;
  return new AssetLoadError('aborted', 'asset load aborted', { retryable: false });
}

async function runAttempt<T>(
  attemptFn: (ctx: AttemptContext) => Promise<T>,
  attempt: number,
  timeoutMs: number,
  outerSignal: AbortSignal | undefined,
  sleep: SleepFn,
  onTimeout: ((attempt: number) => void) | undefined,
): Promise<T> {
  const ac = new AbortController();
  const onOuterAbort = (): void => ac.abort(outerSignal?.reason);
  if (outerSignal) {
    if (outerSignal.aborted) ac.abort(outerSignal.reason);
    else outerSignal.addEventListener('abort', onOuterAbort, { once: true });
  }

  const timeoutPromise = sleep(timeoutMs, ac.signal).then(() => {
    if (!ac.signal.aborted) {
      onTimeout?.(attempt);
      ac.abort(new AssetLoadError('timeout', `attempt ${attempt} timed out`, { retryable: true }));
      throw new AssetLoadError('timeout', `attempt ${attempt} timed out`, { retryable: true });
    }
    return undefined as never;
  });

  try {
    return await Promise.race([attemptFn({ attempt, signal: ac.signal }), timeoutPromise]);
  } catch (err) {
    // If the outer signal aborted, surface an abort error (non-retryable).
    if (outerSignal?.aborted) throw abortError(outerSignal.reason);
    throw err;
  } finally {
    if (outerSignal) outerSignal.removeEventListener('abort', onOuterAbort);
    ac.abort(); // stop the timeout sleep; its promise resolves (no rejection)
    timeoutPromise.catch(() => {
      /* swallow the post-settlement timeout rejection */
    });
  }
}

/** Run `attempt` with the retry state machine. Returns the first success or throws
 * the terminal error (non-retryable, exhausted retries, or abort). */
export async function runWithRetry<T>(opts: RetryOptions<T>): Promise<T> {
  const policy: RetryPolicy = { ...DEFAULT_RETRY_POLICY, ...opts.policy };
  const sleep = opts.sleep ?? defaultSleep;
  const isRetryable = opts.isRetryable ?? isRetryableError;
  const outer = opts.signal;

  let lastErr: unknown;
  for (let i = 0; i <= policy.maxRetries; i++) {
    if (outer?.aborted) throw abortError(outer.reason);
    try {
      return await runAttempt(opts.attempt, i + 1, policy.attemptTimeoutMs, outer, sleep, opts.onTimeout);
    } catch (err) {
      lastErr = err;
      if (outer?.aborted) throw abortError(outer.reason);
      if (!isRetryable(err)) throw err;
      if (i === policy.maxRetries) throw err; // retries exhausted
      const delay = policy.backoffMs[i] ?? policy.backoffMs[policy.backoffMs.length - 1] ?? 0;
      opts.onRetry?.({ attempt: i + 1, error: err, delayMs: delay });
      await sleep(delay, outer);
      if (outer?.aborted) throw abortError(outer.reason);
    }
  }
  throw lastErr;
}

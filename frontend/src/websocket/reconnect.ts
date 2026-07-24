/** Exponential backoff with jitter for WebSocket reconnection (§17). */

export interface BackoffOptions {
  baseMs?: number;
  maxMs?: number;
  factor?: number;
  maxAttempts?: number;
  /** Injectable for deterministic tests; defaults to Math.random. */
  random?: () => number;
}

export class Backoff {
  private attempt = 0;
  private readonly baseMs: number;
  private readonly maxMs: number;
  private readonly factor: number;
  private readonly maxAttempts: number;
  private readonly random: () => number;

  constructor(options: BackoffOptions = {}) {
    this.baseMs = options.baseMs ?? 500;
    this.maxMs = options.maxMs ?? 15000;
    this.factor = options.factor ?? 2;
    this.maxAttempts = options.maxAttempts ?? Infinity;
    this.random = options.random ?? Math.random;
  }

  get attempts(): number {
    return this.attempt;
  }

  get exhausted(): boolean {
    return this.attempt >= this.maxAttempts;
  }

  reset(): void {
    this.attempt = 0;
  }

  /** Return the next delay in ms and advance the attempt counter. */
  next(): number {
    const exp = Math.min(this.maxMs, this.baseMs * this.factor ** this.attempt);
    this.attempt += 1;
    // Full jitter: uniform in [exp/2, exp].
    return Math.round(exp / 2 + this.random() * (exp / 2));
  }
}

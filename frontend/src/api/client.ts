/**
 * Low-level HTTP client. Turns the common error envelope into `ApiError` (§13)
 * and never leaks transport internals to callers. `fetch` is injectable so the
 * whole API layer is unit-testable without a network.
 */

import { toApiError } from './errors';

export type FetchLike = typeof fetch;

export interface HttpClientOptions {
  baseUrl?: string;
  fetch?: FetchLike;
}

export class HttpClient {
  private readonly baseUrl: string;
  private readonly fetchFn: FetchLike;

  constructor(options: HttpClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? '';
    this.fetchFn = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const init: RequestInit = { method };
    if (body !== undefined) {
      init.headers = { 'Content-Type': 'application/json' };
      init.body = JSON.stringify(body);
    }
    let response: Response;
    try {
      response = await this.fetchFn(`${this.baseUrl}${path}`, init);
    } catch {
      // Network-level failure: present as a stable, retryable server code.
      throw toApiError(0, {
        error: {
          code: 'DATABASE_UNAVAILABLE',
          message: 'Cannot reach the server.',
          details: {},
          request_id: '',
        },
      });
    }

    const text = await response.text();
    const parsed: unknown = text ? safeJson(text) : undefined;

    if (!response.ok) {
      throw toApiError(response.status, parsed);
    }
    return parsed as T;
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>('GET', path);
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('POST', path, body);
  }
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

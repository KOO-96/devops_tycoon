import { describe, expect, it, vi } from 'vitest';
import { HttpClient } from '../../src/api/client';
import { ApiError } from '../../src/api/errors';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('HttpClient', () => {
  it('returns parsed body on success and sets JSON headers on POST', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }));
    const http = new HttpClient({ fetch: fetchFn });
    const result = await http.post<{ ok: boolean }>('/x', { a: 1 });
    expect(result).toEqual({ ok: true });
    const init = fetchFn.mock.calls[0]![1] as RequestInit;
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"a":1}');
  });

  it('maps the error envelope to a typed ApiError', async () => {
    // Fresh Response per call — a Response body can only be read once.
    const fetchFn = vi.fn().mockImplementation(() =>
      Promise.resolve(
        jsonResponse(409, {
          error: {
            code: 'REVISION_CONFLICT',
            message: 'stale',
            details: { server_revision: 4, provided_revision: 2 },
            request_id: 'req-1',
          },
        }),
      ),
    );
    const http = new HttpClient({ fetch: fetchFn });
    await expect(http.post('/cmd', {})).rejects.toMatchObject({
      code: 'REVISION_CONFLICT',
      requestId: 'req-1',
    });
    try {
      await http.post('/cmd', {});
    } catch (e) {
      const err = e as ApiError;
      expect(err.serverRevision).toBe(4);
      expect(err.providedRevision).toBe(2);
    }
  });

  it('maps a non-envelope error body to INTERNAL_ERROR', async () => {
    const fetchFn = vi.fn().mockResolvedValue(new Response('<html>502</html>', { status: 502 }));
    const http = new HttpClient({ fetch: fetchFn });
    await expect(http.get('/x')).rejects.toMatchObject({ code: 'INTERNAL_ERROR' });
  });

  it('maps a network failure to a stable DATABASE_UNAVAILABLE code', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new TypeError('network'));
    const http = new HttpClient({ fetch: fetchFn });
    await expect(http.get('/x')).rejects.toMatchObject({ code: 'DATABASE_UNAVAILABLE' });
  });
});

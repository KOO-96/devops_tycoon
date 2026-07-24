/** Event store cursor pagination (§16). PostgreSQL is the source of truth. */

import type { HttpClient } from './client';
import type { EventEnvelope, EventListResponse } from './schemas';

const BASE = '/api/v1/game-sessions';
export const DEFAULT_EVENT_LIMIT = 100;
export const MAX_EVENT_LIMIT = 1000;

export interface ListEventsParams {
  afterCursor?: number; // exclusive
  limit?: number;
}

export function listEvents(
  http: HttpClient,
  sessionId: string,
  params: ListEventsParams = {},
): Promise<EventListResponse> {
  const after = params.afterCursor ?? 0;
  const limit = Math.min(params.limit ?? DEFAULT_EVENT_LIMIT, MAX_EVENT_LIMIT);
  const query = `?after_cursor=${after}&limit=${limit}`;
  return http.get<EventListResponse>(
    `${BASE}/${encodeURIComponent(sessionId)}/events${query}`,
  );
}

/**
 * Drain all durable events after `afterCursor` by following pages until a short
 * page is returned. Used to recover after a reload/state loss (§15).
 */
export async function drainEvents(
  http: HttpClient,
  sessionId: string,
  afterCursor: number,
  limit = DEFAULT_EVENT_LIMIT,
): Promise<EventEnvelope[]> {
  const pageSize = Math.min(limit, MAX_EVENT_LIMIT);
  const all: EventEnvelope[] = [];
  let cursor = afterCursor;
  for (;;) {
    const page = await listEvents(http, sessionId, { afterCursor: cursor, limit: pageSize });
    all.push(...page.events);
    if (page.events.length < pageSize) break;
    const last = page.events[page.events.length - 1];
    if (last === undefined) break;
    cursor = last.cursor;
  }
  return all;
}

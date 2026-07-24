/** Session REST endpoints (§8, §9). */

import type { HttpClient } from './client';
import type {
  CreateSessionRequest,
  CreateSessionResponse,
  SessionSummary,
  SnapshotResponse,
} from './schemas';

const BASE = '/api/v1/game-sessions';

export function createSession(
  http: HttpClient,
  req: CreateSessionRequest = {},
): Promise<CreateSessionResponse> {
  // Only contract-defined inputs are ever sent (never a raw BalanceConfig).
  const body: CreateSessionRequest = {};
  if (req.seed !== undefined) body.seed = req.seed;
  if (req.users !== undefined) body.users = req.users;
  return http.post<CreateSessionResponse>(BASE, body);
}

export function getSummary(http: HttpClient, sessionId: string): Promise<SessionSummary> {
  return http.get<SessionSummary>(`${BASE}/${encodeURIComponent(sessionId)}`);
}

export function getSnapshot(http: HttpClient, sessionId: string): Promise<SnapshotResponse> {
  return http.get<SnapshotResponse>(`${BASE}/${encodeURIComponent(sessionId)}/snapshot`);
}

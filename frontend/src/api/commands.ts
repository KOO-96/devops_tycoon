/** Command REST endpoint + typed builders (§10, §11). */

import type { HttpClient } from './client';
import type {
  AnyCommandRequest,
  CommandPayloadMap,
  CommandRequest,
  CommandType,
} from './commandTypes';
import type { CommandResponse } from './schemas';
import { newCommandId } from '../utils/id';

const BASE = '/api/v1/game-sessions';

export function sendCommand(
  http: HttpClient,
  sessionId: string,
  request: AnyCommandRequest,
): Promise<CommandResponse> {
  return http.post<CommandResponse>(
    `${BASE}/${encodeURIComponent(sessionId)}/commands`,
    request,
  );
}

/**
 * Build a typed command request. Generates a fresh `command_id` for a new intent;
 * pass an explicit `commandId` ONLY to retry the exact same intent (§11).
 */
export function buildCommand<T extends CommandType>(
  commandType: T,
  payload: CommandPayloadMap[T],
  options: { expectedRevision?: number; commandId?: string } = {},
): CommandRequest<T> {
  const request: CommandRequest<T> = {
    command_id: options.commandId ?? newCommandId(),
    command_type: commandType,
    payload,
  };
  if (options.expectedRevision !== undefined) {
    request.expected_revision = options.expectedRevision;
  }
  return request;
}

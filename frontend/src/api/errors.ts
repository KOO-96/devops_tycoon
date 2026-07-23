/**
 * Backend error contract (§13). Branch on `code`, never on `message`. The common
 * envelope is `{ error: { code, message, details, request_id } }`.
 */

export const ERROR_CODES = [
  'VALIDATION_ERROR',
  'SESSION_NOT_FOUND',
  'REVISION_CONFLICT',
  'IDEMPOTENCY_CONFLICT',
  'COMMAND_OUT_OF_ORDER',
  'COMMAND_REJECTED',
  'SNAPSHOT_VERSION_UNSUPPORTED',
  'MANUAL_TICK_DISABLED',
  'SIMULATION_EXECUTION_FAILED',
  'DATABASE_UNAVAILABLE',
  'EVENT_BROKER_UNAVAILABLE',
  'INTERNAL_ERROR',
] as const;

export type ErrorCode = (typeof ERROR_CODES)[number];

const CODE_SET = new Set<string>(ERROR_CODES);

export interface ErrorBody {
  code: ErrorCode;
  message: string;
  details: Record<string, unknown>;
  request_id: string;
}

/** Thrown by the API client for any non-2xx response carrying the envelope. */
export class ApiError extends Error {
  readonly code: ErrorCode;
  readonly details: Record<string, unknown>;
  readonly requestId: string;
  readonly status: number;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.details = body.details ?? {};
    this.requestId = body.request_id ?? '';
  }

  /** REVISION_CONFLICT recovery detail (§12). */
  get serverRevision(): number | undefined {
    const v = this.details['server_revision'];
    return typeof v === 'number' ? v : undefined;
  }

  get providedRevision(): number | undefined {
    const v = this.details['provided_revision'];
    return typeof v === 'number' ? v : undefined;
  }
}

function isErrorBody(value: unknown): value is ErrorBody {
  if (typeof value !== 'object' || value === null) return false;
  const code = (value as { code?: unknown }).code;
  return typeof code === 'string' && CODE_SET.has(code);
}

/**
 * Coerce an arbitrary response body into an ApiError. Unknown shapes (proxy
 * errors, HTML, network faults) map to INTERNAL_ERROR so the UI never has to
 * parse free text.
 */
export function toApiError(status: number, body: unknown): ApiError {
  const envelope = (body as { error?: unknown } | null)?.error;
  if (isErrorBody(envelope)) {
    return new ApiError(status, envelope);
  }
  return new ApiError(status, {
    code: 'INTERNAL_ERROR',
    message: 'Unexpected error response.',
    details: {},
    request_id: '',
  });
}

/** True for a well-formed backend error envelope (used by the WS ERROR frame). */
export function parseErrorBody(value: unknown): ErrorBody | null {
  const envelope = (value as { error?: unknown } | null)?.error;
  return isErrorBody(envelope) ? envelope : isErrorBody(value) ? value : null;
}

/** Client id generation for command idempotency keys (§11). */

/**
 * Generate a fresh command_id for a NEW user intent. Retrying the *same* intent
 * must reuse the returned id (never call this again for a retry).
 */
export function newCommandId(): string {
  // crypto.randomUUID is available in modern browsers and Node >= 19.
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Deterministic-enough fallback (tests/older runtimes): not for security.
  return `cmd-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

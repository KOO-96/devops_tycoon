import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { COMMAND_TYPES } from '../../src/api/commandTypes';
import { ERROR_CODES } from '../../src/api/errors';
import { MESSAGE_TYPES } from '../../src/websocket/protocol';

// The Backend OpenAPI file is the source of truth (§3, §7). These tests fail if
// the UI's curated types drift from the contract. Vitest runs with the frontend
// dir as cwd; the contract lives one level up.
const specPath = resolve(process.cwd(), '../contracts/openapi/backend-v1.json');
const spec = JSON.parse(readFileSync(specPath, 'utf8')) as {
  components: { schemas: Record<string, { enum?: string[] }> };
  paths: Record<string, Record<string, { requestBody?: { content: Record<string, { schema: { discriminator?: { mapping: Record<string, string> } } }> } }>>;
};

describe('UI ↔ OpenAPI contract alignment', () => {
  it('command types match the discriminated-union mapping', () => {
    const body = spec.paths['/api/v1/game-sessions/{session_id}/commands']?.post?.requestBody;
    const mapping = body?.content['application/json']?.schema.discriminator?.mapping ?? {};
    expect(new Set(Object.keys(mapping))).toEqual(new Set(COMMAND_TYPES));
  });

  it('error codes match the ErrorCode enum', () => {
    const enumValues = spec.components.schemas['ErrorCode']?.enum ?? [];
    expect(new Set(enumValues)).toEqual(new Set(ERROR_CODES));
  });

  it('exposes exactly the six WebSocket message types the client handles', () => {
    // Not in OpenAPI (WS lives in a markdown contract); assert the local list is
    // the agreed set so it cannot silently diverge.
    expect(new Set(MESSAGE_TYPES)).toEqual(
      new Set(['SESSION_SNAPSHOT', 'SESSION_STATE', 'DOMAIN_EVENT', 'COMMAND_RESULT', 'ERROR', 'HEARTBEAT']),
    );
  });
});

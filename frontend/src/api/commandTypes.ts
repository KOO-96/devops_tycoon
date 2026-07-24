/**
 * Typed command request contract (§10). One payload type per supported command;
 * mirrors `contracts/commands/backend-command-v1.md` and the OpenAPI discriminated
 * union. Frontend NEVER sends `sequence`. `target` lives inside `payload`.
 */

import type { Health, NodeKind } from './schemas';

export type CommandType =
  | 'ADD_NODE'
  | 'REMOVE_NODE'
  | 'CONNECT'
  | 'DISCONNECT'
  | 'SET_LB_CONFIG'
  | 'ENABLE_SERVER'
  | 'DISABLE_SERVER'
  | 'SET_REDIS_CONFIG'
  | 'SET_DB_POOL'
  | 'DEPLOY'
  | 'ROLLBACK'
  | 'DISABLE_FEATURE'
  | 'PAUSE'
  | 'SET_SPEED';

export const COMMAND_TYPES: readonly CommandType[] = [
  'ADD_NODE',
  'REMOVE_NODE',
  'CONNECT',
  'DISCONNECT',
  'SET_LB_CONFIG',
  'ENABLE_SERVER',
  'DISABLE_SERVER',
  'SET_REDIS_CONFIG',
  'SET_DB_POOL',
  'DEPLOY',
  'ROLLBACK',
  'DISABLE_FEATURE',
  'PAUSE',
  'SET_SPEED',
] as const;

export type LbAlgorithm = 'round_robin' | 'weighted' | 'least_conn';

// --- per-command payloads --------------------------------------------------

export interface AddNodePayload {
  target: string;
  node_kind: NodeKind;
  weight?: number;
  queue_capacity?: number;
  mem_leak_per_tick?: number;
  max_connections?: number;
}
export interface TargetOnlyPayload {
  target: string;
}
export interface EdgePayload {
  target: string;
  to: string;
}
export interface SetLbConfigPayload {
  target: string;
  algorithm?: LbAlgorithm;
  sticky?: boolean;
}
export interface SetRedisConfigPayload {
  target: string;
  ttl_ticks?: number;
  capacity_entries?: number;
  enabled?: boolean;
}
export interface SetDbPoolPayload {
  target: string;
  max_connections?: number;
}
export interface DeployPayload {
  target: string;
  version?: string;
  mem_leak_per_tick?: number;
}
export interface RollbackPayload {
  target: string;
  to_version: string;
}
export interface DisableFeaturePayload {
  target?: string;
}
export interface PausePayload {
  paused: boolean;
}
export interface SetSpeedPayload {
  speed: number;
}

export interface CommandPayloadMap {
  ADD_NODE: AddNodePayload;
  REMOVE_NODE: TargetOnlyPayload;
  CONNECT: EdgePayload;
  DISCONNECT: EdgePayload;
  SET_LB_CONFIG: SetLbConfigPayload;
  ENABLE_SERVER: TargetOnlyPayload;
  DISABLE_SERVER: TargetOnlyPayload;
  SET_REDIS_CONFIG: SetRedisConfigPayload;
  SET_DB_POOL: SetDbPoolPayload;
  DEPLOY: DeployPayload;
  ROLLBACK: RollbackPayload;
  DISABLE_FEATURE: DisableFeaturePayload;
  PAUSE: PausePayload;
  SET_SPEED: SetSpeedPayload;
}

/** A command request body for a specific command_type. */
export interface CommandRequest<T extends CommandType = CommandType> {
  command_id: string;
  command_type: T;
  expected_revision?: number;
  payload: CommandPayloadMap[T];
}

export type AnyCommandRequest = {
  [K in CommandType]: CommandRequest<K>;
}[CommandType];

// Visual-only helper for mapping health to a node kind is elsewhere; re-export
// Health so command UIs can reason about node states without a second import.
export type { Health, NodeKind };

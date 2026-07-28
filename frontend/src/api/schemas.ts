/**
 * Curated UI-facing contract types. These mirror the Backend OpenAPI contract
 * (`contracts/openapi/backend-v1.json`), which is the source of truth; the
 * generated types live in `src/api/generated/backend.d.ts` and are used to keep
 * this file honest (see tests/api/contract.test.ts). Hand-written here so the UI
 * is not coupled to generated naming.
 */

// --- session ---------------------------------------------------------------

export interface CreateSessionRequest {
  seed?: number;
  users?: number;
}

export interface CreateSessionResponse {
  session_id: string;
  status: string;
  revision: number;
  current_tick: number;
  state_version: number;
  created_at: string;
}

export interface EconomySummary {
  cash: number | null;
  revenue_total: number | null;
  cost_total: number | null;
}

export interface IncidentSummary {
  type: string | null;
  target: string | null;
  phase: string | null;
}

export interface SessionSummary {
  session_id: string;
  status: string;
  revision: number;
  current_tick: number;
  speed: number;
  paused: boolean;
  economy: EconomySummary;
  user_trust: number | null;
  investor_trust: number | null;
  active_incidents: IncidentSummary[];
  updated_at: string;
}

export interface SnapshotResponse {
  session_id: string;
  revision: number;
  simulation_state_version: number;
  snapshot: SimulationSnapshot;
}

// --- simulation snapshot (read-only projection) ----------------------------

export type NodeKind = 'load_balancer' | 'app_server' | 'redis' | 'postgresql';
export type Health = 'Healthy' | 'Warning' | 'Critical' | 'Down';

export interface SnapshotNode {
  id: string;
  kind: NodeKind;
  enabled: boolean;
  // Optional: the snapshot is a free-form object and some kinds (load_balancer)
  // omit health entirely. A missing value is resolved to not_applicable/
  // not_reported by the status resolver — never defaulted to Healthy.
  health?: Health;
  cpu_usage?: number;
  mem_usage?: number;
  queue_length?: number;
  queue_capacity?: number;
  max_connections?: number;
  [key: string]: unknown;
}

export interface SimulationSnapshot {
  version: number;
  simulation_id: string;
  clock: { tick: number; tick_ms: number; speed: number; paused: boolean };
  users?: number;
  load_balancers: Record<string, SnapshotNode>;
  app_servers: Record<string, SnapshotNode>;
  caches: Record<string, SnapshotNode>;
  databases: Record<string, SnapshotNode>;
  connections: Array<[string, string]>;
  economy?: { cash: number; revenue_total: number; cost_total: number };
  user_trust?: number;
  investor_trust?: number;
  [key: string]: unknown;
}

// --- events ----------------------------------------------------------------

export interface EventEnvelope {
  event_id: string;
  cursor: number;
  session_id: string;
  session_revision: number;
  tick: number;
  type: string;
  target: string | null;
  payload: Record<string, unknown>;
}

export interface EventListResponse {
  session_id: string;
  events: EventEnvelope[];
}

// --- commands --------------------------------------------------------------

export type CommandStatus =
  | 'APPLIED'
  | 'ALREADY_APPLIED'
  | 'DUPLICATE_COMMAND_ID'
  | 'COMMAND_OUT_OF_ORDER'
  | 'COMMAND_REJECTED';

export interface CommandResponse {
  command_id: string;
  sequence: number;
  status: CommandStatus;
  reason_code: string | null;
  session_revision: number;
  current_tick: number;
  events: EventEnvelope[];
  state_summary: Record<string, unknown>;
}

/**
 * Formal Client Runtime Source Classes (POLICY-C-FU-001, FE-ART-002).
 *
 * Every visual state has ONE authoritative data source. Operational status comes
 * from the Backend contract (health enum / enabled field / incident / capability);
 * everything else is a legitimate *client* runtime state — selection, connection,
 * snapshot-sync, asset-runtime — that the Backend does not report and the Frontend
 * MUST NOT dress up as operational health.
 *
 * This module is the single place that names those classes and maps a state key
 * to its class, so components can never invent a source or render, say, a
 * "Reconnecting" socket as a Warning node, or an asset fallback as a Down node.
 *
 * NOTE: `EVENT_DERIVED` is intentionally NOT part of this PR's usable set — no
 * event-driven visual effect ships until POLICY-C-FU-002 (event lifecycle) is
 * confirmed. It is omitted here so nothing can accidentally consume it.
 */

import type { NodeVisualStatus, StatusAppearance } from './nodeStatus';
import { statusAppearance } from './nodeStatus';

export type VisualStateSourceClass =
  | 'SNAPSHOT_DIRECT'
  | 'HEALTH_ENUM'
  | 'ENABLED_FIELD'
  | 'INCIDENT_DERIVED'
  | 'CAPABILITY_DERIVED'
  | 'CLIENT_LOCAL'
  | 'CLIENT_CONNECTION'
  | 'CLIENT_SYNC'
  | 'ASSET_RUNTIME';

/** Client-local visual state keys (selection / hover / focus). */
export type ClientLocalStateKey = 'Selected' | 'Unselected' | 'Hovered' | 'Focused';
/** Connection visual state keys (socket lifecycle, NOT node health). */
export type ClientConnectionStateKey = 'Connecting' | 'Connected' | 'Reconnecting' | 'Disconnected';
/** Snapshot sync visual state keys (post-command refresh, NOT node health). */
export type ClientSyncStateKey =
  | 'SnapshotLoading'
  | 'SnapshotRefreshing'
  | 'SnapshotSyncFailed'
  | 'RevisionConflict';
/** Asset runtime visual state keys (texture load, NOT backend errors). */
export type AssetRuntimeStateKey =
  | 'AssetLoading'
  | 'AssetUnavailable'
  | 'FallbackActive'
  | 'ManifestStale'
  | 'AssetRetrying';

/** A resolved visual state with an explicit, authoritative source class. */
export interface VisualStateDescriptor {
  sourceClass: VisualStateSourceClass;
  stateKey: string;
  shortText: string;
  ariaText: string;
  /** Stable tone token; NOT a health colour for client states. */
  tone: string;
  glyph: string;
}

// The source class of each client state key is fixed — a component may not choose.
const CLIENT_LOCAL_SOURCE: Record<ClientLocalStateKey, VisualStateSourceClass> = {
  Selected: 'CLIENT_LOCAL',
  Unselected: 'CLIENT_LOCAL',
  Hovered: 'CLIENT_LOCAL',
  Focused: 'CLIENT_LOCAL',
};
const CLIENT_CONNECTION_SOURCE: Record<ClientConnectionStateKey, VisualStateSourceClass> = {
  Connecting: 'CLIENT_CONNECTION',
  Connected: 'CLIENT_CONNECTION',
  Reconnecting: 'CLIENT_CONNECTION',
  Disconnected: 'CLIENT_CONNECTION',
};
const CLIENT_SYNC_SOURCE: Record<ClientSyncStateKey, VisualStateSourceClass> = {
  SnapshotLoading: 'CLIENT_SYNC',
  SnapshotRefreshing: 'CLIENT_SYNC',
  SnapshotSyncFailed: 'CLIENT_SYNC',
  RevisionConflict: 'CLIENT_SYNC',
};
const ASSET_RUNTIME_SOURCE: Record<AssetRuntimeStateKey, VisualStateSourceClass> = {
  AssetLoading: 'ASSET_RUNTIME',
  AssetUnavailable: 'ASSET_RUNTIME',
  FallbackActive: 'ASSET_RUNTIME',
  ManifestStale: 'ASSET_RUNTIME',
  AssetRetrying: 'ASSET_RUNTIME',
};

const CLIENT_LOCAL_DESCRIPTOR: Record<ClientLocalStateKey, Omit<VisualStateDescriptor, 'sourceClass' | 'stateKey'>> = {
  Selected: { shortText: 'Selected', ariaText: 'selected', tone: 'accent', glyph: '◉' },
  Unselected: { shortText: 'Not selected', ariaText: 'not selected', tone: 'muted', glyph: '○' },
  Hovered: { shortText: 'Hovered', ariaText: 'hovered', tone: 'accent', glyph: '◍' },
  Focused: { shortText: 'Focused', ariaText: 'focused', tone: 'accent', glyph: '◎' },
};
const CLIENT_CONNECTION_DESCRIPTOR: Record<ClientConnectionStateKey, Omit<VisualStateDescriptor, 'sourceClass' | 'stateKey'>> = {
  Connecting: { shortText: 'Connecting', ariaText: 'connecting to session', tone: 'info', glyph: '…' },
  Connected: { shortText: 'Connected', ariaText: 'connected', tone: 'ok', glyph: '↔' },
  Reconnecting: { shortText: 'Reconnecting', ariaText: 'reconnecting to session', tone: 'info', glyph: '↻' },
  Disconnected: { shortText: 'Disconnected', ariaText: 'disconnected from session', tone: 'muted', glyph: '⦸' },
};
const CLIENT_SYNC_DESCRIPTOR: Record<ClientSyncStateKey, Omit<VisualStateDescriptor, 'sourceClass' | 'stateKey'>> = {
  SnapshotLoading: { shortText: 'Loading board', ariaText: 'loading board', tone: 'info', glyph: '…' },
  SnapshotRefreshing: { shortText: 'Refreshing', ariaText: 'refreshing board', tone: 'info', glyph: '↻' },
  SnapshotSyncFailed: { shortText: 'Sync failed', ariaText: 'board sync failed', tone: 'warn', glyph: '⚠' },
  RevisionConflict: { shortText: 'Out of date', ariaText: 'board out of date', tone: 'warn', glyph: '⚠' },
};
const ASSET_RUNTIME_DESCRIPTOR: Record<AssetRuntimeStateKey, Omit<VisualStateDescriptor, 'sourceClass' | 'stateKey'>> = {
  AssetLoading: { shortText: 'Loading art', ariaText: 'loading artwork', tone: 'info', glyph: '…' },
  AssetUnavailable: { shortText: 'Art unavailable', ariaText: 'artwork unavailable, placeholder shown', tone: 'muted', glyph: '▢' },
  FallbackActive: { shortText: 'Placeholder art', ariaText: 'placeholder artwork', tone: 'muted', glyph: '▢' },
  ManifestStale: { shortText: 'Art updating', ariaText: 'artwork updating', tone: 'info', glyph: '↻' },
  AssetRetrying: { shortText: 'Retrying art', ariaText: 'retrying artwork load', tone: 'info', glyph: '↻' },
};

export function clientLocalDescriptor(key: ClientLocalStateKey): VisualStateDescriptor {
  return { sourceClass: CLIENT_LOCAL_SOURCE[key], stateKey: key, ...CLIENT_LOCAL_DESCRIPTOR[key] };
}
export function clientConnectionDescriptor(key: ClientConnectionStateKey): VisualStateDescriptor {
  return { sourceClass: CLIENT_CONNECTION_SOURCE[key], stateKey: key, ...CLIENT_CONNECTION_DESCRIPTOR[key] };
}
export function clientSyncDescriptor(key: ClientSyncStateKey): VisualStateDescriptor {
  return { sourceClass: CLIENT_SYNC_SOURCE[key], stateKey: key, ...CLIENT_SYNC_DESCRIPTOR[key] };
}
export function assetRuntimeDescriptor(key: AssetRuntimeStateKey): VisualStateDescriptor {
  return { sourceClass: ASSET_RUNTIME_SOURCE[key], stateKey: key, ...ASSET_RUNTIME_DESCRIPTOR[key] };
}

/** The authoritative source class for an operational node status. Health values
 * are HEALTH_ENUM, disabled is ENABLED_FIELD, and a missing/absent value is
 * CAPABILITY_DERIVED (never invented, never a false Healthy). */
export function nodeStatusSourceClass(status: NodeVisualStatus): VisualStateSourceClass {
  switch (status.kind) {
    case 'health':
      return 'HEALTH_ENUM';
    case 'disabled':
      return 'ENABLED_FIELD';
    case 'not_applicable':
    case 'not_reported':
      return 'CAPABILITY_DERIVED';
  }
}

/** Build a descriptor for an operational node status, carrying its source class
 * and the shared appearance so canvas and DOM stay in agreement. */
export function nodeStatusDescriptor(status: NodeVisualStatus): VisualStateDescriptor {
  const appearance: StatusAppearance = statusAppearance(status);
  return {
    sourceClass: nodeStatusSourceClass(status),
    stateKey: appearance.toneKey,
    shortText: appearance.shortText,
    ariaText: appearance.ariaText,
    tone: appearance.toneKey,
    glyph: appearance.glyph,
  };
}

/** Incidents are INCIDENT_DERIVED — separate from health, never a severity the
 * Frontend invents. */
export const INCIDENT_SOURCE_CLASS: VisualStateSourceClass = 'INCIDENT_DERIVED';

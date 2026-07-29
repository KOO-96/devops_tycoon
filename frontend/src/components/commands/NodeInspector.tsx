/**
 * Inspector for the selected node + the minimal supported per-node commands
 * (§10, §20). Only real, supported commands are exposed; unsupported actions are
 * simply not shown (never a dead button).
 */

import { useState } from 'react';
import { useController } from '../../session/controllerContext';
import { useGameSessionStore } from '../../state/gameSessionStore';
import type { NodeKind, SnapshotNode } from '../../api/schemas';
import { nodeStatusAppearance } from '../../game/nodeStatus';

function findNode(store: ReturnType<typeof useGameSessionStore.getState>, id: string | null): SnapshotNode | null {
  if (id === null || store.snapshot === null) return null;
  const s = store.snapshot;
  for (const group of [s.load_balancers, s.app_servers, s.caches, s.databases]) {
    const node = group?.[id];
    if (node) return node;
  }
  return null;
}

const KINDS: NodeKind[] = ['load_balancer', 'app_server', 'redis', 'postgresql'];

export function NodeInspector(): JSX.Element {
  const controller = useController();
  const selectedId = useGameSessionStore((s) => s.selectedNodeId);
  const snapshot = useGameSessionStore((s) => s.snapshot);
  const pending = useGameSessionStore((s) => s.pending);
  const node = findNode(useGameSessionStore.getState(), selectedId);

  const [newId, setNewId] = useState('');
  const [newKind, setNewKind] = useState<NodeKind>('app_server');

  const busy = (key: string): boolean => key in pending;

  const addNode = (): void => {
    const target = newId.trim();
    if (target === '') return;
    void controller.runCommand(`ADD_NODE:${target}`, 'ADD_NODE', { target, node_kind: newKind });
    setNewId('');
  };

  return (
    <section aria-label="Node inspector">
      <h2 style={{ fontSize: '0.9rem' }}>Inspector</h2>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          addNode();
        }}
        style={{ marginBottom: '0.75rem' }}
      >
        <label>
          New node id{' '}
          <input value={newId} onChange={(e) => setNewId(e.target.value)} aria-label="New node id" />
        </label>
        <label>
          {' '}
          Kind{' '}
          <select value={newKind} onChange={(e) => setNewKind(e.target.value as NodeKind)} aria-label="Node kind">
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>{' '}
        <button type="submit" disabled={newId.trim() === '' || busy(`ADD_NODE:${newId.trim()}`)}>
          Add
        </button>
      </form>

      {node === null ? (
        <p>Select a node on the board or in the list to inspect it.</p>
      ) : (
        <div>
          <p>
            <strong>{node.id}</strong> — {node.kind} ·{' '}
            {(() => {
              const a = nodeStatusAppearance({ kind: node.kind, enabled: node.enabled, health: node.health });
              return (
                <span className={`status-${a.toneKey}`} aria-label={a.ariaText}>
                  {a.glyph} {a.shortText}
                </span>
              );
            })()}
          </p>
          <dl style={{ fontSize: '0.8rem' }}>
            {typeof node.cpu_usage === 'number' && (
              <div>
                <dt>CPU</dt>
                <dd>{node.cpu_usage.toFixed(1)}</dd>
              </div>
            )}
            {typeof node.mem_usage === 'number' && (
              <div>
                <dt>Memory</dt>
                <dd>{node.mem_usage.toFixed(1)}</dd>
              </div>
            )}
            {typeof node.queue_length === 'number' && (
              <div>
                <dt>Queue</dt>
                <dd>
                  {node.queue_length}
                  {typeof node.queue_capacity === 'number' ? ` / ${node.queue_capacity}` : ''}
                </dd>
              </div>
            )}
          </dl>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {node.kind === 'app_server' &&
              (node.enabled ? (
                <button
                  type="button"
                  disabled={busy(`DISABLE_SERVER:${node.id}`)}
                  onClick={() =>
                    void controller.runCommand(`DISABLE_SERVER:${node.id}`, 'DISABLE_SERVER', {
                      target: node.id,
                    })
                  }
                >
                  Disable
                </button>
              ) : (
                <button
                  type="button"
                  disabled={busy(`ENABLE_SERVER:${node.id}`)}
                  onClick={() =>
                    void controller.runCommand(`ENABLE_SERVER:${node.id}`, 'ENABLE_SERVER', {
                      target: node.id,
                    })
                  }
                >
                  Enable
                </button>
              ))}
            <button
              type="button"
              disabled={busy(`REMOVE_NODE:${node.id}`)}
              onClick={() =>
                void controller.runCommand(`REMOVE_NODE:${node.id}`, 'REMOVE_NODE', { target: node.id })
              }
            >
              Remove
            </button>
          </div>
        </div>
      )}
      {snapshot === null && <p style={{ color: '#8a97a8' }}>Snapshot not loaded.</p>}
    </section>
  );
}

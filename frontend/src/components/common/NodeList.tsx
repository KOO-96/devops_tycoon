/**
 * Accessible DOM node list — the keyboard/screen-reader alternative to canvas
 * selection (§25). Selecting here drives the same store selection as the Pixi
 * board, so the two stay in sync.
 */

import { useGameSessionStore } from '../../state/gameSessionStore';
import { snapshotToBoardNodes, nodeStatusText } from '../../game/pixi/nodes';

export function NodeList(): JSX.Element {
  const snapshot = useGameSessionStore((s) => s.snapshot);
  const selected = useGameSessionStore((s) => s.selectedNodeId);
  const select = useGameSessionStore((s) => s.select);
  const nodes = snapshotToBoardNodes(snapshot);

  return (
    <nav aria-label="Infrastructure nodes" className="node-list">
      <h2 style={{ fontSize: '0.9rem' }}>Nodes ({nodes.length})</h2>
      {nodes.length === 0 && <p>No nodes yet. Add one to build your system.</p>}
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {nodes.map((node) => (
          <li key={node.id}>
            <button
              type="button"
              aria-pressed={selected === node.id}
              onClick={() => select(selected === node.id ? null : node.id)}
            >
              <span className={`status-${node.health}`} aria-hidden="true">
                ●{' '}
              </span>
              {nodeStatusText(node)}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

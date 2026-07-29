/**
 * Accessible DOM node list — the keyboard/screen-reader alternative to canvas
 * selection (§25). Selecting here drives the same store selection as the Pixi
 * board, so the two stay in sync.
 */

import { useGameSessionStore } from '../../state/gameSessionStore';
import { snapshotToBoardNodes, nodeStatusText, nodeStatusAria } from '../../game/pixi/nodes';
import { nodeStatusAppearance } from '../../game/nodeStatus';

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
        {nodes.map((node) => {
          const appearance = nodeStatusAppearance(node);
          return (
            <li key={node.id}>
              <button
                type="button"
                aria-pressed={selected === node.id}
                aria-label={nodeStatusAria(node)}
                onClick={() => select(selected === node.id ? null : node.id)}
              >
                <span className={`status-${appearance.toneKey}`} aria-hidden="true">
                  {appearance.glyph}{' '}
                </span>
                {nodeStatusText(node)}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/**
 * Center campus frame (§13): title + status strip + the existing GameCanvas with
 * connection/empty overlays. The Pixi canvas/renderer is unchanged; overlays are
 * pointer-events:none so canvas input is never blocked.
 */

import { GameCanvas } from '../../game/GameCanvas';
import { ErrorRegion } from '../common/ErrorRegion';
import { SnapshotSyncBanner } from '../common/SnapshotSyncBanner';
import { useConnectionStore } from '../../state/connectionStore';
import { useGameSessionStore } from '../../state/gameSessionStore';
import { snapshotToBoardNodes } from '../../game/pixi/nodes';

export function CampusFrame(): JSX.Element {
  const sessionId = useGameSessionStore((s) => s.sessionId);
  const snapshot = useGameSessionStore((s) => s.snapshot);
  const socketStatus = useConnectionStore((s) => s.socketStatus);
  const nodeCount = snapshotToBoardNodes(snapshot).length;

  const reconnecting = socketStatus === 'reconnecting' || socketStatus === 'connecting';
  const dropped = socketStatus === 'disconnected' || socketStatus === 'failed';

  return (
    <main id="campus-main" className="campus-frame" aria-label="Campus board">
      <div className="campus-title">
        <span>Campus{sessionId ? ` · ${sessionId.slice(0, 8)}…` : ''}</span>
        <span className="visually-hidden">
          Use the Nodes list in the side panel for keyboard access to the board.
        </span>
      </div>
      <div style={{ padding: 'var(--s-8)' }}>
        <ErrorRegion />
        <SnapshotSyncBanner />
      </div>
      <div className="campus-canvas-wrap">
        <GameCanvas />
        {reconnecting && (
          <div className="campus-overlay" role="status" aria-live="polite">
            <div className="campus-overlay-card">Reconnecting to live updates…</div>
          </div>
        )}
        {dropped && (
          <div className="campus-overlay" role="status" aria-live="polite">
            <div className="campus-overlay-card">
              Live connection lost — no data is lost. Reconnecting or use the events list to recover.
            </div>
          </div>
        )}
        {!reconnecting && !dropped && nodeCount === 0 && (
          <div className="campus-overlay">
            <div className="campus-overlay-card">
              No nodes yet. Use <strong>Build</strong> in the inspector to add your first server.
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

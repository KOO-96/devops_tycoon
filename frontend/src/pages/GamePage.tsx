/** Main game screen: single bootstrap + load-state gating (§2, §5, §10). */

import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useController } from '../session/controllerContext';
import { useGameSessionStore } from '../state/gameSessionStore';
import { Hud } from '../components/hud/Hud';
import { ControlBar } from '../components/hud/ControlBar';
import { ConnectionBanner } from '../components/common/ConnectionBanner';
import { ErrorRegion } from '../components/common/ErrorRegion';
import { SnapshotSyncBanner } from '../components/common/SnapshotSyncBanner';
import { SessionErrorScreen } from '../components/common/SessionErrorScreen';
import { NodeList } from '../components/common/NodeList';
import { IncidentPanel } from '../components/incidents/IncidentPanel';
import { NodeInspector } from '../components/commands/NodeInspector';
import { EventLog } from '../components/events/EventLog';
import { GameCanvas } from '../game/GameCanvas';

export function GamePage(): JSX.Element {
  const { sessionId } = useParams<{ sessionId: string }>();
  const controller = useController();
  const navigate = useNavigate();
  const loadState = useGameSessionStore((s) => s.loadState);
  const loadError = useGameSessionStore((s) => s.loadError);
  const activeSessionId = useGameSessionStore((s) => s.sessionId);

  useEffect(() => {
    if (sessionId === undefined) return;
    // One bootstrap path for new-game, direct URL, reload, and session switch.
    void controller.bootstrapSession(sessionId);
    return () => controller.teardown();
  }, [sessionId, controller]);

  const startNewGame = (): void => {
    void controller
      .startNewGame()
      .then((id) => navigate(`/game/${id}`))
      .catch(() => navigate('/'));
  };
  const backToStart = (): void => navigate('/');

  if (loadState === 'not_found' || loadState === 'recoverable_error' || loadState === 'fatal_error') {
    return (
      <SessionErrorScreen
        kind={loadState}
        sessionId={activeSessionId ?? sessionId ?? null}
        error={loadError}
        onNewGame={startNewGame}
        onBackToStart={backToStart}
        {...(loadState === 'recoverable_error'
          ? { onRetry: () => void controller.retry() }
          : {})}
      />
    );
  }

  if (loadState !== 'ready') {
    return (
      <main style={{ maxWidth: 520, margin: '4rem auto', padding: '0 1rem' }} aria-busy="true">
        <p role="status" aria-live="polite">
          Loading game session…
        </p>
      </main>
    );
  }

  return (
    <div>
      <ConnectionBanner />
      <Hud />
      <ControlBar />
      <SnapshotSyncBanner />
      <ErrorRegion />
      <div className="game-layout">
        <div>
          <GameCanvas />
        </div>
        <aside className="sidebar">
          <NodeInspector />
          <NodeList />
          <IncidentPanel />
          <EventLog />
        </aside>
      </div>
    </div>
  );
}

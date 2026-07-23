/** Main game screen: board + HUD + panels, wired to the live session (§9, §20). */

import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useController } from '../session/controllerContext';
import { useGameSessionStore } from '../state/gameSessionStore';
import { Hud } from '../components/hud/Hud';
import { ControlBar } from '../components/hud/ControlBar';
import { ConnectionBanner } from '../components/common/ConnectionBanner';
import { ErrorRegion } from '../components/common/ErrorRegion';
import { NodeList } from '../components/common/NodeList';
import { IncidentPanel } from '../components/incidents/IncidentPanel';
import { NodeInspector } from '../components/commands/NodeInspector';
import { EventLog } from '../components/events/EventLog';
import { GameCanvas } from '../game/GameCanvas';

const SUMMARY_REFRESH_MS = 3000;

export function GamePage(): JSX.Element {
  const { sessionId } = useParams<{ sessionId: string }>();
  const controller = useController();
  const storeSessionId = useGameSessionStore((s) => s.sessionId);

  useEffect(() => {
    if (sessionId === undefined) return;
    // Attach if we arrived cold (reload / deep link) — resume rebuilds from
    // snapshot + event replay (§15). If the controller already created this
    // session, it is already connected.
    if (storeSessionId !== sessionId) {
      void controller.resume(sessionId).catch(() => undefined);
    }
    // Lightweight summary refresh keeps the HUD current without a client tick
    // scheduler (out of scope §5). Snapshot/board updates arrive via events.
    const timer = setInterval(() => {
      void controller.refreshSummary(sessionId).catch(() => undefined);
    }, SUMMARY_REFRESH_MS);

    return () => {
      clearInterval(timer);
      controller.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  return (
    <div>
      <ConnectionBanner />
      <Hud />
      <ControlBar />
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

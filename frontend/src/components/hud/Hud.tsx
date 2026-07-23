/** Head-up display (§20): tick/speed/pause/economy/trust/incidents + connection. */

import { useConnectionStore } from '../../state/connectionStore';
import { useGameSessionStore } from '../../state/gameSessionStore';

function fmt(n: number | null | undefined, digits = 0): string {
  return typeof n === 'number' ? n.toFixed(digits) : '—';
}

export function Hud(): JSX.Element {
  const summary = useGameSessionStore((s) => s.summary);
  const currentTick = useGameSessionStore((s) => s.currentTick);
  const revision = useGameSessionStore((s) => s.revision);
  const socketStatus = useConnectionStore((s) => s.socketStatus);

  const incidents = summary?.active_incidents ?? [];

  return (
    <dl className="hud" aria-label="Game status">
      <div>
        <dt>Tick</dt>
        <dd>{currentTick}</dd>
      </div>
      <div>
        <dt>Revision</dt>
        <dd>{revision}</dd>
      </div>
      <div>
        <dt>Speed</dt>
        <dd>{summary ? `${summary.speed}×` : '—'}</dd>
      </div>
      <div>
        <dt>State</dt>
        <dd>{summary?.paused ? 'Paused' : 'Running'}</dd>
      </div>
      <div>
        <dt>Cash</dt>
        <dd>{fmt(summary?.economy.cash)}</dd>
      </div>
      <div>
        <dt>Revenue</dt>
        <dd>{fmt(summary?.economy.revenue_total)}</dd>
      </div>
      <div>
        <dt>User trust</dt>
        <dd>{fmt(summary?.user_trust, 1)}</dd>
      </div>
      <div>
        <dt>Incidents</dt>
        <dd className={incidents.length > 0 ? 'status-Critical' : undefined}>{incidents.length}</dd>
      </div>
      <div>
        <dt>Connection</dt>
        <dd>{socketStatus}</dd>
      </div>
    </dl>
  );
}

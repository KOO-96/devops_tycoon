/** Active incident list (§19, §20). */

import { useGameSessionStore } from '../../state/gameSessionStore';

export function IncidentPanel(): JSX.Element {
  const incidents = useGameSessionStore((s) => s.summary?.active_incidents ?? []);

  return (
    <section aria-label="Active incidents">
      <h2 style={{ fontSize: '0.9rem' }}>Incidents ({incidents.length})</h2>
      {incidents.length === 0 ? (
        <p>No active incidents.</p>
      ) : (
        <ul style={{ paddingLeft: '1rem', margin: 0 }}>
          {incidents.map((inc, i) => (
            <li key={`${inc.type ?? 'incident'}-${inc.target ?? i}`} className="status-Critical">
              {inc.type ?? 'Incident'} @ {inc.target ?? 'system'} ({inc.phase ?? 'active'})
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

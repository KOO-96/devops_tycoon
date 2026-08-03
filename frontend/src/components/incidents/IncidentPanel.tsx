/** Active incident list (§19, §20). Uses the shared incident overlay model so the
 * DOM list is deduped, phase-ordered, and bounded exactly like the canvas overlay
 * (POLICY-C-FU-003). Phase is shown as reported — never converted to a severity. */

import { useGameSessionStore } from '../../state/gameSessionStore';
import { buildIncidentOverlayModel } from '../../game/incidentModel';

const PHASE_TONE: Record<string, string> = {
  ACTIVE: 'status-Critical',
  WARNING: 'status-Warning',
  RECOVERING: 'status-Warning',
  RECOVERED: 'status-Disabled',
};

export function IncidentPanel(): JSX.Element {
  const incidents = useGameSessionStore((s) => s.summary?.active_incidents ?? []);
  const model = buildIncidentOverlayModel(incidents);

  return (
    <section aria-label="Active incidents">
      <h2 style={{ fontSize: '0.9rem' }}>Incidents ({model.total})</h2>
      {model.total === 0 ? (
        <p>No active incidents.</p>
      ) : (
        <>
          <ul style={{ paddingLeft: '1rem', margin: 0 }} role="list">
            {model.visible.map((inc) => (
              <li key={inc.key} className={PHASE_TONE[inc.phase] ?? 'status-Critical'}>
                {inc.type} @ {inc.target} ({inc.phase})
              </li>
            ))}
          </ul>
          {model.overflowCount > 0 && (
            <p aria-label="More incidents" style={{ margin: '0.25rem 0 0' }}>
              +{model.overflowCount} more
            </p>
          )}
        </>
      )}
    </section>
  );
}

/**
 * Right context panel (§14): composes the existing (working, tested) inspector /
 * node list / incident / event components as card sections. No data-source or
 * logic changes — layout/styling only. Current Task / Mission intentionally
 * omitted (Phase 3 / campaign).
 */

import { NodeInspector } from '../commands/NodeInspector';
import { NodeList } from '../common/NodeList';
import { IncidentPanel } from '../incidents/IncidentPanel';
import { EventLog } from '../events/EventLog';

export function ContextPanel(): JSX.Element {
  return (
    <aside className="context-panel" aria-label="Context panel">
      <div className="panel">
        <NodeInspector />
      </div>
      <div className="panel">
        <NodeList />
      </div>
      <div className="panel">
        <IncidentPanel />
      </div>
      <div className="panel">
        <EventLog />
      </div>
    </aside>
  );
}

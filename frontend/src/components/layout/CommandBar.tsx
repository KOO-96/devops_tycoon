/**
 * Bottom command bar (§15) — hosts GLOBAL commands (pause / speed via the existing
 * ControlBar). Node-specific commands live in the right-panel inspector, so
 * commands are never duplicated across the nav and this bar.
 */

import { ControlBar } from '../hud/ControlBar';

export function CommandBar(): JSX.Element {
  return (
    <div className="command-bar" role="group" aria-label="Global commands">
      <span className="metric-label" style={{ paddingRight: 'var(--s-8)' }}>
        Simulation
      </span>
      <ControlBar />
    </div>
  );
}

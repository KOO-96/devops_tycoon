/** Top header: brand + HUD metrics + connection status (§11). */

import { Hud } from '../hud/Hud';
import { ConnectionBanner } from '../common/ConnectionBanner';

export function TopHud(): JSX.Element {
  return (
    <header className="top-hud">
      <div className="brand" aria-label="DevOps Tycoon">
        DevOps <span style={{ color: 'var(--c-interactive)' }}>Tycoon</span>
      </div>
      <Hud />
      <div style={{ marginLeft: 'auto' }}>
        <ConnectionBanner />
      </div>
    </header>
  );
}

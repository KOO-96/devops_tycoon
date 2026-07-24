/**
 * Game page layout shell (§10): CSS-grid composition of header / left-nav /
 * campus / context / command regions with semantic landmarks (header/nav/main/
 * aside) + a skip link. Renders the same child components as before, so all
 * behavior and tests are preserved; this only reorganizes and styles them.
 */

import { TopHud } from './TopHud';
import { LeftNavigation } from './LeftNavigation';
import { CampusFrame } from './CampusFrame';
import { ContextPanel } from './ContextPanel';
import { CommandBar } from './CommandBar';

export function GameLayout(): JSX.Element {
  return (
    <div className="game-shell">
      <a className="skip-link" href="#campus-main">
        Skip to campus
      </a>
      <TopHud />
      <LeftNavigation />
      <CampusFrame />
      <ContextPanel />
      <CommandBar />
    </div>
  );
}

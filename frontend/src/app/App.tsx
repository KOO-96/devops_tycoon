/** Root application shell. */

import { AppProviders } from './providers';
import { AppRoutes } from './routes';
import { AppShell } from '../components/layout/AppShell';
import type { GameSessionController } from '../session/controller';

export function App({ controller }: { controller?: GameSessionController }): JSX.Element {
  return (
    <AppProviders {...(controller ? { controller } : {})}>
      <AppShell>
        <AppRoutes />
      </AppShell>
    </AppProviders>
  );
}

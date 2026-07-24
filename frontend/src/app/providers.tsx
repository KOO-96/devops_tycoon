/** App-wide providers (§6). */

import type { ReactNode } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { ControllerProvider } from '../session/controllerContext';
import type { GameSessionController } from '../session/controller';

export function AppProviders({
  children,
  controller,
}: {
  children: ReactNode;
  controller?: GameSessionController;
}): JSX.Element {
  return (
    <BrowserRouter>
      <ControllerProvider {...(controller ? { controller } : {})}>{children}</ControllerProvider>
    </BrowserRouter>
  );
}

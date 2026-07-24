/** React context providing the singleton GameSessionController (§6 providers). */

import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { GameSessionController } from './controller';
import { browserWebSocketFactory, config } from '../config';

const ControllerContext = createContext<GameSessionController | null>(null);

export function ControllerProvider({
  children,
  controller,
}: {
  children: ReactNode;
  controller?: GameSessionController;
}): JSX.Element {
  const value = useMemo(
    () =>
      controller ??
      new GameSessionController({
        baseUrl: config.baseUrl,
        baseWsUrl: config.baseWsUrl,
        createWebSocket: browserWebSocketFactory,
      }),
    [controller],
  );
  return <ControllerContext.Provider value={value}>{children}</ControllerContext.Provider>;
}

export function useController(): GameSessionController {
  const controller = useContext(ControllerContext);
  if (controller === null) throw new Error('useController must be used within ControllerProvider');
  return controller;
}

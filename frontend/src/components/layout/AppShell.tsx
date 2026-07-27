/** App-wide background wrapper (bright sky vista, CSS only). */

import type { ReactNode } from 'react';

export function AppShell({ children }: { children: ReactNode }): JSX.Element {
  return <div className="app-bg">{children}</div>;
}

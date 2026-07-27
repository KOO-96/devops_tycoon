/** Standalone section heading (when Panel's built-in title isn't used). */

import type { ReactNode } from 'react';

export function SectionHeader({ children }: { children: ReactNode }): JSX.Element {
  return <h2 className="panel-header">{children}</h2>;
}

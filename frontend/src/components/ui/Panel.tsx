/** Card surface with an optional accessible heading (SectionHeader). */

import type { ReactNode } from 'react';

export function Panel({
  title,
  action,
  labelledById,
  children,
}: {
  title?: string;
  action?: ReactNode;
  labelledById?: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <section className="panel" {...(labelledById ? { 'aria-labelledby': labelledById } : {})}>
      {title !== undefined && (
        <h2 className="panel-header" {...(labelledById ? { id: labelledById } : {})}>
          <span>{title}</span>
          {action}
        </h2>
      )}
      {children}
    </section>
  );
}

/** Explicit empty/placeholder state (never a blank white box — §14). */

export function EmptyState({ children }: { children: string }): JSX.Element {
  return <p className="empty-state">{children}</p>;
}

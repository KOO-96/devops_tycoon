/** Status pill: colour + glyph + text (never colour alone — §19/a11y). */

export type StatusTone = 'healthy' | 'warning' | 'critical' | 'down' | 'info' | 'muted';

const GLYPH: Record<StatusTone, string> = {
  healthy: '✔',
  warning: '!',
  critical: '‼',
  down: '✕',
  info: 'ℹ',
  muted: '•',
};

export function StatusBadge({ tone, label }: { tone: StatusTone; label: string }): JSX.Element {
  return (
    <span className="status-badge" data-tone={tone}>
      <span aria-hidden="true">{GLYPH[tone]}</span>
      {label}
    </span>
  );
}

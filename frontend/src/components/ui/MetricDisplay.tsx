/** Label + tabular value pair for the HUD / metrics. */

export function MetricDisplay({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: 'critical' | 'warning' | undefined;
}): JSX.Element {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <span
        className="metric-value"
        {...(tone ? { style: { color: tone === 'critical' ? 'var(--c-critical)' : 'var(--c-warning)' } } : {})}
      >
        {value}
      </span>
    </div>
  );
}

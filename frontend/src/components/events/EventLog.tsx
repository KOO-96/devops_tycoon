/** Recent domain-event feed (§19). Bounded in the store; newest first here. */

import { useGameSessionStore } from '../../state/gameSessionStore';

export function EventLog(): JSX.Element {
  const events = useGameSessionStore((s) => s.events);
  const recent = events.slice(-30).reverse();

  return (
    <section aria-label="Recent events">
      <h2 style={{ fontSize: '0.9rem' }}>Events</h2>
      <ol style={{ listStyle: 'none', padding: 0, margin: 0, fontFamily: 'monospace', fontSize: '0.75rem' }}>
        {recent.map((e) => (
          <li key={e.event_id}>
            <span style={{ color: '#8a97a8' }}>t{e.tick}</span> {e.type}
            {e.target !== null && <span> → {e.target}</span>}
          </li>
        ))}
      </ol>
    </section>
  );
}

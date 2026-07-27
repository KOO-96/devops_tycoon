/**
 * Left navigation shell (§12). Selection + panel-switch shell only — no fake
 * backend behavior. All MVP-active items currently focus the same campus view;
 * real per-item views are a later PR. Research is disabled (Coming Later).
 */

import { useState } from 'react';

type NavStatus = 'active' | 'readonly' | 'disabled';
interface NavItem {
  id: string;
  label: string;
  glyph: string;
  status: NavStatus;
  tag?: string;
}

const ITEMS: NavItem[] = [
  { id: 'campus', label: 'Campus', glyph: '⌂' },
  { id: 'build', label: 'Build', glyph: '＋' },
  { id: 'connect', label: 'Connect', glyph: '↔' },
  { id: 'deploy', label: 'Deploy', glyph: '⤴' },
  { id: 'monitor', label: 'Monitor', glyph: '📈', status: 'readonly', tag: 'read-only' },
  { id: 'research', label: 'Research', glyph: '💡', status: 'disabled', tag: 'soon' },
].map((i) => ({ status: 'active' as NavStatus, ...i })) as NavItem[];

export function LeftNavigation(): JSX.Element {
  const [selected, setSelected] = useState('campus');
  return (
    <nav className="left-nav" aria-label="Campus sections">
      {ITEMS.map((item) => {
        const disabled = item.status === 'disabled';
        const current = selected === item.id;
        return (
          <button
            key={item.id}
            type="button"
            className="nav-item"
            aria-disabled={disabled || undefined}
            aria-current={current ? 'page' : undefined}
            onClick={() => {
              if (!disabled) setSelected(item.id);
            }}
          >
            <span className="nav-glyph" aria-hidden="true">
              {item.glyph}
            </span>
            <span className="nav-label">{item.label}</span>
            {item.tag !== undefined && <span className="nav-tag">{item.tag}</span>}
          </button>
        );
      })}
    </nav>
  );
}

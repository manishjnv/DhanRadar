/** S12 "Momentum Center" — 30d/90d/1y tabs + climbing/falling rank columns. */
'use client';
import * as React from 'react';
import { cn } from '@/lib/cn';
import { Logo } from './Logo';
import { MOMENTUM, type MomRow } from './sampleData';

const TABS: { key: '30d' | '90d' | '1y'; label: string }[] = [
  { key: '30d', label: 'Last 30 Days' },
  { key: '90d', label: '90 Days' },
  { key: '1y',  label: '1 Year' },
];

function Col({ title, rows, tone }: { title: string; rows: MomRow[]; tone: 'up' | 'down' }) {
  return (
    <div>
      <h4 className={cn('text-small font-semibold flex items-center gap-1.5 mb-2', tone === 'up' ? 'text-emerald' : 'text-red')}>
        {tone === 'up' ? '▲ Climbing rankings' : '▼ Falling rankings'}
      </h4>
      <ul>
        {rows.map((r, i) => (
          <li key={i} className="flex items-center gap-2.5 py-2 border-b border-line last:border-0">
            <Logo letter={r.logo} color={r.color} size={26} />
            <span className="flex-1 text-small font-medium text-ink truncate">{r.name}</span>
            <span className={cn('font-mono text-small font-semibold', tone === 'up' ? 'text-emerald' : 'text-red')}>{r.val} ranks</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Momentum() {
  const [tab, setTab] = React.useState<'30d' | '90d' | '1y'>('30d');
  const data = MOMENTUM[tab];
  return (
    <div>
      <div className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5 mb-3" role="group" aria-label="Momentum window">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            aria-pressed={tab === t.key}
            className={cn(
              'rounded-md px-3 py-1.5 text-small font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
              tab === t.key ? 'bg-surface text-ink shadow-sm' : 'text-ink-muted hover:text-ink',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="rounded-xl border border-line bg-surface p-5 shadow-sm grid gap-6 sm:grid-cols-2">
        <Col title="up" rows={data.up} tone="up" />
        <Col title="down" rows={data.down} tone="down" />
      </div>
    </div>
  );
}

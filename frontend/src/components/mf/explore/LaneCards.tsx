/**
 * LaneCards — reused for S5 "AI Discovery" and S11 "Fund Flow".
 * Each lane = an icon/tag header + rows of (logo · name · value).
 * Pure presentational over illustrative data (see sampleData.ts).
 */
'use client';
import * as React from 'react';
import { cn } from '@/lib/cn';
import { Logo } from './Logo';
import type { DiscoveryLane } from './sampleData';

export function LaneCards({ lanes, cols = 4 }: { lanes: DiscoveryLane[]; cols?: 3 | 4 }) {
  return (
    <div className={cn('grid gap-3', cols === 4 ? 'sm:grid-cols-2 lg:grid-cols-4' : 'sm:grid-cols-2 lg:grid-cols-3')}>
      {lanes.map((lane) => (
        <div key={lane.tag} className="rounded-xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center gap-2 mb-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg text-base" style={{ background: lane.bg, color: lane.color }} aria-hidden="true">
              {lane.icon}
            </span>
            <span className="text-small font-semibold text-ink">{lane.tag}</span>
          </div>
          <ul>
            {lane.rows.map((r, i) => (
              <li key={i} className="flex items-center gap-2.5 py-2 border-b border-line last:border-0">
                <Logo letter={r.logo} color={r.color} size={24} />
                <span className="flex-1 text-small font-medium text-ink truncate">{r.name}</span>
                <span className="font-mono text-small font-semibold" style={{ color: lane.color }}>{r.val}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

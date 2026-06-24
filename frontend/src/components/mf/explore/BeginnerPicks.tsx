/**
 * S15 "Beginner Picks" — illustrative. V4's "Who should buy / avoid" is reframed
 * to educational "Often suits / Less suited for" (no advisory verbs).
 */
'use client';
import * as React from 'react';
import { Logo } from './Logo';
import { BEGINNER } from './sampleData';

export function BeginnerPicks() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {BEGINNER.map((b) => (
        <div key={b.tag} className="rounded-xl border border-line bg-surface p-4 shadow-sm">
          <span className="inline-flex items-center font-mono text-caption font-semibold uppercase tracking-wide px-2 py-0.5 rounded-md" style={{ background: `${b.color}1A`, color: b.color }}>
            {b.tag}
          </span>
          <div className="mt-3 flex items-center gap-2.5">
            <Logo letter={b.logo} color={b.logoColor} size={36} />
            <div className="text-small font-semibold text-ink">{b.short}</div>
          </div>
          <div className="mt-3 space-y-2.5">
            <div>
              <div className="text-caption font-semibold uppercase tracking-wide text-ink-secondary">Why this fund?</div>
              <p className="text-small text-ink-muted leading-relaxed mt-0.5">{b.why}</p>
            </div>
            <div>
              <div className="text-caption font-semibold uppercase tracking-wide text-emerald">Often suits</div>
              <p className="text-small text-ink-muted leading-relaxed mt-0.5">{b.suits}</p>
            </div>
            <div>
              <div className="text-caption font-semibold uppercase tracking-wide text-amber">Less suited for</div>
              <p className="text-small text-ink-muted leading-relaxed mt-0.5">{b.lessFor}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

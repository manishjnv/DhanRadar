/**
 * S10 "DMMI Market Leaders" — V4 layout, made compliant.
 *  - Semicircular sentiment gauge shows a regime WORD, NEVER a number (non-neg #2).
 *  - Uses the real /market/mood regime word + commentary when available, else the
 *    illustrative DMMI sample.
 *  - V4's "Suggested SIP/lumpsum action" is reframed to EDUCATIONAL context cards
 *    (no directives — non-neg #1). Best/weakest category lists are illustrative.
 */
'use client';
import * as React from 'react';
import { cn } from '@/lib/cn';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { REGIME_DISPLAY } from '@/components/mood/MoodGauge';
import { useMoodCurrent } from '@/features/mood/api';
import { DMMI } from './sampleData';

// Semicircular arc gauge — fill is visual-only; NO numeric is ever rendered.
function Gauge({ fill, word, sub, color }: { fill: number; word: string; sub: string; color: string }) {
  const W = 220, R = 90, CX = W / 2, CY = 110, STROKE = 14;
  const a0 = Math.PI, a1 = Math.PI * (1 - fill);
  const p = (a: number) => `${CX + R * Math.cos(a)} ${CY - R * Math.sin(a)}`;
  const track = `M ${p(Math.PI)} A ${R} ${R} 0 0 1 ${p(0)}`;
  const active = `M ${p(a0)} A ${R} ${R} 0 0 1 ${p(a1)}`;
  return (
    <figure className="inline-flex flex-col items-center m-0">
      <svg width={W} height={130} viewBox={`0 0 ${W} 130`} aria-hidden="true" focusable="false">
        <path d={track} fill="none" stroke="var(--border)" strokeWidth={STROKE} strokeLinecap="round" />
        <path d={active} fill="none" stroke={color} strokeWidth={STROKE} strokeLinecap="round" />
      </svg>
      <figcaption className="text-center -mt-3">
        <div className="text-h3 font-semibold" style={{ color }}>{word}</div>
        <div className="text-caption text-ink-muted mt-0.5">{sub}</div>
      </figcaption>
    </figure>
  );
}

export function DmmiSection() {
  const { data } = useMoodCurrent();
  const healthy = data && data.data_quality !== 'unavailable' && data.regime !== 'data_unavailable' && data.regime !== 'insufficient_data';
  const word = healthy ? REGIME_DISPLAY[data!.regime] : DMMI.word;
  const commentary = (healthy && data?.commentary) ? data.commentary : null;

  return (
    <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">
      <div className="grid gap-6 md:grid-cols-[260px_1fr] md:items-center">
        <div className="flex justify-center">
          <Gauge fill={DMMI.fill} word={word} sub={DMMI.sub} color="var(--dr-royal,#1E5EFF)" />
        </div>
        <div>
          <div className="grid gap-3 sm:grid-cols-2">
            {DMMI.notes.map((n) => (
              <div key={n.title} className="rounded-xl border border-line p-4">
                <div className={cn('text-caption font-semibold uppercase tracking-wide mb-1.5', n.tone === 'up' ? 'text-emerald' : 'text-cyan')}>{n.title}</div>
                <p className="text-small text-ink-secondary leading-relaxed">{n.body}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <h5 className="text-caption font-semibold uppercase tracking-wide text-emerald mb-2">Stronger categories now</h5>
              <ul>
                {DMMI.best.map((b) => (
                  <li key={b.n} className="flex items-center justify-between py-1.5 border-b border-line last:border-0 text-small">
                    <span className="font-medium text-ink">{b.n}</span><span className="text-emerald font-semibold text-caption">{b.d}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h5 className="text-caption font-semibold uppercase tracking-wide text-amber mb-2">Weaker categories now</h5>
              <ul>
                {DMMI.weak.map((w) => (
                  <li key={w.n} className="flex items-center justify-between py-1.5 border-b border-line last:border-0 text-small">
                    <span className="font-medium text-ink">{w.n}</span><span className="text-amber font-semibold text-caption">{w.d}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
      {commentary && <p className="mt-4 text-small text-ink-secondary leading-relaxed border-t border-line pt-4">{commentary}</p>}
      <div className="mt-4 border-t border-line pt-4">
        <DisclosureBundle
          disclosure={healthy ? (data?.disclosure || undefined) : undefined}
          notAdvice={healthy ? (data?.not_advice || 'Market mood is educational only — not investment advice.') : 'Market mood is educational only — not investment advice. Sample data shown.'}
        />
      </div>
    </div>
  );
}

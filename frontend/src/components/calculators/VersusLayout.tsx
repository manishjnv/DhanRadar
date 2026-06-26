'use client';

/**
 * VersusLayout — shared presentation for the "Versus" comparison calculators
 * (§12). Renders 2–3 options side by side, a NEUTRAL verdict line, and a caveat
 * panel (risk / tax / liquidity). The "winner" is only ever marked "for your
 * inputs" — factual on the user's own numbers, never a recommendation.
 */
import * as React from 'react';
import { Panel } from './ui';

export type VsOption = {
  label: string; // "SIP" / "Lumpsum"
  headline: string; // formatted hero figure, e.g. "₹1.25 Cr"
  headlineLabel: string; // what the hero figure is, e.g. "Final value (after tax)"
  rows: { label: string; value: string }[];
  winner?: boolean; // higher/cheaper FOR THE USER'S INPUTS (not a recommendation)
};

export function VersusLayout({ options, verdict, caveats }: {
  options: VsOption[];
  verdict: React.ReactNode;
  caveats: string[];
}) {
  return (
    <>
      <div className={`grid grid-cols-1 gap-3 ${options.length >= 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
        {options.map((o) => (
          <Panel key={o.label} className={o.winner ? 'ring-2 ring-royal' : ''}>
            <div className="flex items-center justify-between gap-2">
              <span className="text-small font-semibold text-ink">{o.label}</span>
              {o.winner && (
                <span className="shrink-0 rounded-full bg-royal/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.04em] text-royal">For your inputs</span>
              )}
            </div>
            <div className="mt-2 font-mono text-[22px] font-medium tracking-[-0.02em] text-ink">{o.headline}</div>
            <div className="text-caption tracking-normal text-ink-muted">{o.headlineLabel}</div>
            <div className="mt-3">
              {o.rows.map((r) => (
                <div key={r.label} className="flex items-center justify-between border-b border-line py-1.5 last:border-b-0">
                  <span className="text-small text-ink-secondary">{r.label}</span>
                  <span className="font-mono text-small font-semibold text-ink">{r.value}</span>
                </div>
              ))}
            </div>
          </Panel>
        ))}
      </div>

      <Panel className="mt-3.5">
        <div className="text-small leading-relaxed text-ink">{verdict}</div>
      </Panel>

      {caveats.length > 0 && (
        <Panel className="mt-3 border-amber/30 bg-amber/5">
          <div className="mb-1.5 text-caption font-semibold uppercase tracking-[0.04em] text-amber">Read before you compare</div>
          <ul className="space-y-1.5">
            {caveats.map((c, i) => (
              <li key={i} className="flex gap-2 text-caption leading-relaxed text-ink-secondary">
                <span aria-hidden="true" className="text-amber">•</span><span>{c}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </>
  );
}

/**
 * Fund Comparison V3 — shared presentational primitives.
 *
 * Ported from the approved FundComparisonPageV3 desktop + mobile mockups into
 * Geist/warm Tailwind tokens. Responsive by construction: comparison tables
 * scroll horizontally inside their card (no page-level horizontal scroll at any
 * breakpoint), card grids collapse to a single column on small screens.
 *
 * COMPLIANCE: nothing here renders a DhanRadar-computed numeric score. Computed
 * scores arrive pre-mapped to strength words (see sampleData.toStrength); only
 * factual published metrics (returns, NAV, ratios) appear as plain values.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { StrengthBar } from '@/components/mf/funddetail/parts';
import type { Strength } from '@/components/mf/funddetail/sampleData';
import { FUNDS, type CompareFund, type Row, toStrength } from './sampleData';

// ───────────────────────────────────────────────────────────────────────────
// "So what" insight strip (was .sowhat)
// ───────────────────────────────────────────────────────────────────────────
export function SoWhat({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3.5 flex gap-2.5 rounded-xl bg-royal/[0.06] px-3.5 py-3 text-small leading-relaxed text-ink-secondary">
      <span className="shrink-0 font-bold text-royal" aria-hidden="true">→</span>
      <p className="m-0">{children}</p>
    </div>
  );
}

// Bold-aware text (renders **bold** spans from sample strings)
export function RichText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith('**') && p.endsWith('**') ? (
          <b key={i} className="font-semibold text-ink">{p.slice(2, -2)}</b>
        ) : (
          <React.Fragment key={i}>{p}</React.Fragment>
        ),
      )}
    </>
  );
}

export function Panel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cn('rounded-2xl border border-line bg-surface p-4 shadow-sm sm:p-5', className)}>{children}</section>;
}

// Preview badge (illustrative data)
export function Preview({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border border-line bg-surface-2 px-2 py-0.5',
        'font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-muted',
        className,
      )}
      title="Illustrative preview data — real feed coming"
    >
      <span aria-hidden="true">◴</span> Preview
    </span>
  );
}

// Win / accent chip (was .winchip)
export function WinChip({ children, gold }: { children: React.ReactNode; gold?: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[10px] font-bold',
        gold ? 'bg-amber/15 text-amber' : 'bg-emerald/10 text-emerald',
      )}
    >
      {children}
    </span>
  );
}

// Fund-coloured dot
export function Dot({ color, size = 10 }: { color: string; size?: number }) {
  return <span className="inline-block shrink-0 rounded-sm align-middle" style={{ width: size, height: size, background: color }} />;
}

// ───────────────────────────────────────────────────────────────────────────
// CompareTable — fund columns, factual values, winner cell highlighted.
// Horizontally scrollable inside its card → safe at every breakpoint.
// ───────────────────────────────────────────────────────────────────────────
function winnerIndex(row: Row): number {
  if (!row.win) return -1;
  const nums = row.vals.map((v) => (v == null ? NaN : parseFloat(String(v).replace(/[^0-9.\-]/g, ''))));
  const valid = nums.filter((n) => !Number.isNaN(n));
  if (!valid.length) return -1;
  const ext = row.win === 'low' ? Math.min(...valid.map(Math.abs)) : Math.max(...valid);
  return nums.findIndex((n) => !Number.isNaN(n) && (row.win === 'low' ? Math.abs(n) : n) === ext);
}

export function CompareTable({
  rows,
  firstCol = 'Metric',
  showCategory = false,
  verdict,
  funds = FUNDS,
}: {
  rows: Row[];
  firstCol?: string;
  showCategory?: boolean;
  verdict?: [string, string][];
  funds?: CompareFund[];
}) {
  return (
    <div className="-mx-1 overflow-x-auto">
      <table className="w-full border-collapse text-small">
        <thead>
          <tr>
            <th className="border-b-2 border-line px-3 py-2.5 text-left font-mono text-[11px] font-bold uppercase tracking-[0.04em] text-ink-muted">{firstCol}</th>
            {funds.map((f) => (
              <th key={f.key} className="border-b-2 border-line px-3 py-2.5 text-center font-mono text-[11px] font-bold uppercase tracking-[0.04em] text-ink-muted">
                <span className="inline-flex items-center gap-1.5"><Dot color={f.color} size={8} />{f.short}</span>
              </th>
            ))}
            {showCategory && <th className="border-b-2 border-line px-3 py-2.5 text-right font-mono text-[11px] font-bold uppercase tracking-[0.04em] text-ink-muted">Category</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const wi = winnerIndex(row);
            const valid = row.vals.map((v) => (v == null ? NaN : parseFloat(String(v).replace(/[^0-9.\-]/g, '')))).filter((n) => !Number.isNaN(n));
            const catVal = showCategory && valid.length ? (Math.min(...valid) * 0.9).toFixed(1) + '%' : null;
            return (
              <tr key={row.label}>
                <td className="border-b border-line px-3 py-2.5 text-left font-medium text-ink-secondary">{row.label}</td>
                {row.vals.map((v, i) => (
                  <td
                    key={i}
                    className={cn(
                      'border-b border-line px-3 py-2.5 text-center font-mono font-semibold',
                      v == null && 'text-ink-faint',
                      i === wi ? 'rounded bg-emerald/10 text-emerald' : 'text-ink',
                      row.tone === 'neg' && i !== wi && 'text-red',
                      row.tone === 'pos' && i !== wi && 'text-emerald',
                    )}
                  >
                    {v == null ? '—' : `${v}${typeof v === 'number' ? '%' : ''}`}
                  </td>
                ))}
                {showCategory && <td className="border-b border-line px-3 py-2.5 text-right font-mono text-ink-faint">{catVal ?? '—'}</td>}
              </tr>
            );
          })}
          {verdict && (
            <tr>
              <td className="px-3 py-2.5 text-left font-medium text-ink-secondary">Educational read</td>
              {verdict.map(([word, color], i) => (
                <td key={i} className="px-3 py-2.5 text-center">
                  <span className="rounded-md px-2 py-0.5 font-mono text-[10px] font-bold" style={{ background: `${color}1A`, color }}>{word}</span>
                </td>
              ))}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// ScoreboardRows — computed scores → StrengthBar word per fund (no number).
// ───────────────────────────────────────────────────────────────────────────
export function ScoreboardRows({ rows }: { rows: { metric: string; scores: number[] }[] }) {
  return (
    <div className="flex flex-col divide-y divide-line">
      {rows.map((r) => {
        const strengths = r.scores.map(toStrength);
        const rank: Record<Strength, number> = { strong: 4, good: 3, moderate: 2, soft: 1 };
        const best = Math.max(...strengths.map((s) => rank[s]));
        return (
          <div key={r.metric} className="py-3">
            <div className="mb-2 flex items-center gap-1.5 text-small font-medium text-ink-secondary">{r.metric}</div>
            <div className="grid gap-1.5">
              {FUNDS.map((f, i) => (
                <div key={f.key} className="flex items-center gap-2">
                  <Dot color={f.color} size={8} />
                  <span className="w-16 shrink-0 text-caption text-ink-muted">{f.short}</span>
                  <div className="flex-1">
                    <StrengthBar name="" strength={strengths[i]} />
                  </div>
                  {rank[strengths[i]] === best && <span className="text-[10px]" aria-hidden="true">🏆</span>}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Heat row table (risk traffic-light)
const HEAT = ['#00B386', '#F5A623', '#E5484D'];
export function HeatTable({ rows }: { rows: { label: string; vals: string[]; better: 'low' | 'hi' }[] }) {
  return (
    <div className="-mx-1 overflow-x-auto">
      <table className="w-full border-collapse text-small">
        <thead>
          <tr>
            <th className="border-b-2 border-line px-3 py-2.5 text-left font-mono text-[11px] font-bold uppercase tracking-[0.04em] text-ink-muted">Risk metric</th>
            {FUNDS.map((f) => (
              <th key={f.key} className="border-b-2 border-line px-3 py-2.5 text-center font-mono text-[11px] font-bold uppercase tracking-[0.04em] text-ink-muted">
                <span className="inline-flex items-center gap-1.5"><Dot color={f.color} size={8} />{f.short}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const nums = r.vals.map((v) => parseFloat(String(v).replace(/[^0-9.\-]/g, '')));
            const order = nums.map((v, i) => [r.better === 'hi' ? v : Math.abs(v), i] as [number, number]).sort((a, b) => (r.better === 'hi' ? b[0] - a[0] : a[0] - b[0]));
            const rankOf: Record<number, number> = {};
            order.forEach(([, i], rank) => (rankOf[i] = rank));
            return (
              <tr key={r.label}>
                <td className="border-b border-line px-3 py-2 text-left font-medium text-ink-secondary">{r.label}</td>
                {r.vals.map((v, i) => {
                  const col = HEAT[rankOf[i]] ?? HEAT[1];
                  return (
                    <td key={i} className="border-b border-line px-2 py-2 text-center">
                      <span className="inline-block min-w-[60px] rounded-lg px-2 py-1.5 font-mono text-caption font-bold" style={{ background: `${col}1F`, color: col }}>{v}</span>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Card-action button (educational CTAs only — "View"/"Details", never "Invest")
export function CTA({ children, variant = 'ghost', className, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'navy' | 'ghost' }) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-small font-semibold transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
        variant === 'primary' && 'bg-royal text-white hover:bg-royal/90',
        variant === 'navy' && 'bg-navy text-white hover:opacity-90',
        variant === 'ghost' && 'border border-line bg-surface-2 text-ink hover:bg-surface-3',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

export type { CompareFund };

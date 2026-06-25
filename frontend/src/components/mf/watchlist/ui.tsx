/**
 * Watchlist Monitor — presentational primitives.
 *
 * Ported 1:1 from the approved WatchlistPageV1 mockup into Geist/warm Tailwind
 * tokens. Responsive by construction: grids collapse, rails scroll inside their
 * own track, tables scroll inside their card — no page-level horizontal scroll.
 *
 * Generic, hydration-safe primitives (Card, SoWhat, RichText, CTA, Logo,
 * BandRing, Semicircle, Donut) are reused from the Portfolio module rather than
 * duplicated. Watchlist-specific atoms live here.
 *
 * COMPLIANCE BRIDGE: score rings render a BAND fill with no inner number, and
 * verdict/momentum pills use educational labels — never advisory verbs or a raw
 * 0–100 composite score (non-neg #1 + #2).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';

// Reused, proven, hydration-safe primitives.
export { Logo, BandRing, Semicircle, Donut, Card, SoWhat, RichText, CTA } from '@/components/mf/portfolio/ui';

// ── Sparkline (deterministic, seeded — no Date/Math.random at render) ─────────
function lcg(seed: number) {
  let s = seed % 233280 || 1;
  return () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
}
export function Spark({ seed, up, width = 290, height = 30, color }: { seed: number; up: boolean; width?: number; height?: number; color?: string }) {
  const N = 26;
  const rnd = lcg(seed);
  const data: number[] = [];
  let v = 50;
  for (let i = 0; i < N; i++) { v += (rnd() - 0.5) * 4 + (up ? 0.4 : -0.35); data.push(v); }
  const lo = Math.min(...data);
  const hi = Math.max(...data);
  const range = hi - lo || 1;
  const stepX = width / (N - 1);
  const pts = data.map((d, i) => [i * stepX, height - ((d - lo) / range) * (height - 2) - 1]);
  const line = 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
  const col = color ?? (up ? '#00B386' : '#E5484D');
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="block w-full" aria-hidden="true">
      <path d={`${line} L ${width},${height} L 0,${height} Z`} fill={col} opacity={0.12} />
      <path d={line} fill="none" stroke={col} strokeWidth={1.5} strokeLinecap="round" />
    </svg>
  );
}

// ── Verdict / status pill (educational label) ────────────────────────────────
export function Pill({ label, color, className }: { label: string; color: string; className?: string }) {
  return (
    <span
      className={cn('inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono text-[10px] font-bold whitespace-nowrap', className)}
      style={{ background: `${color}1A`, color }}
    >
      {label}
    </span>
  );
}

// ── Filter chip ──────────────────────────────────────────────────────────────
export function Chip({ label, count, active, onClick }: { label: string; count?: number; active?: boolean; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-caption font-semibold shadow-sm transition-colors whitespace-nowrap',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
        active
          ? 'border-navy bg-navy text-white'
          : 'border-line bg-surface text-ink-secondary hover:border-royal hover:text-royal',
      )}
    >
      {label}
      {count != null && <span className={cn('font-mono text-[10px]', active ? 'opacity-80' : 'opacity-60')}>{count}</span>}
    </button>
  );
}

// ── Small metric tile (3Y / 5Y / SIP / Cost) ─────────────────────────────────
export function MetricTile({ value, label, tone }: { value: React.ReactNode; label: string; tone?: 'pos' | 'neg' }) {
  return (
    <div className="rounded-lg bg-surface-2 px-1.5 py-2 text-center">
      <div className={cn('font-mono text-xs font-bold', tone === 'pos' && 'text-emerald', tone === 'neg' && 'text-red')}>{value}</div>
      <div className="mt-0.5 text-[8.5px] font-semibold uppercase text-ink-muted">{label}</div>
    </div>
  );
}

// ── Tiny inline brand chip (used in "what changed" rows) ─────────────────────
export function MiniLogo({ letter, color }: { letter: string; color: string }) {
  return (
    <span
      className="mr-1.5 inline-grid h-[18px] w-[18px] place-items-center rounded-[5px] align-middle font-sans text-[9px] font-extrabold text-white"
      style={{ background: color }}
      aria-hidden="true"
    >
      {letter}
    </span>
  );
}

// ── Soft pill (DMMI / AUM tags on a fund card) ───────────────────────────────
export function SoftPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-surface-2 px-2 py-0.5 text-[10px] font-semibold text-ink-secondary">
      {children}
    </span>
  );
}

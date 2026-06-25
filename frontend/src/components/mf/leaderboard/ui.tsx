/**
 * Rankings & Leaderboards V1 — shared presentational primitives.
 *
 * Ported 1:1 from the approved LeaderboardPageV1 desktop + mobile mockups into
 * Geist/warm Tailwind tokens. Responsive by construction — rails scroll inside
 * their own track, tables scroll inside their card, grids collapse on small
 * screens, so there is no page-level horizontal scroll at any breakpoint.
 *
 * COMPLIANCE BRIDGE (visual design untouched): score rings render a BAND fill
 * with no inner number, and quality columns render strength WORDS — never a raw
 * DhanRadar 0–100 score (non-neg #2). Verdict pills use educational labels
 * (non-neg #1). See sampleData.ts for the mapping helpers.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { toBand, ringColor, riskColor } from './sampleData';

const BAND_FILL: Record<'high' | 'medium' | 'low', number> = { high: 0.85, medium: 0.55, low: 0.3 };

// ── Brand-letter tile ────────────────────────────────────────────────────────
export function Logo({ letter, color, size = 34, radius = 9, font = 13 }: { letter: string; color: string; size?: number; radius?: number; font?: number }) {
  return (
    <span
      className="grid shrink-0 place-items-center font-sans font-extrabold text-white"
      style={{ width: size, height: size, borderRadius: radius, background: color, fontSize: font }}
      aria-hidden="true"
    >
      {letter}
    </span>
  );
}

// ── Score band ring (NO number — band-driven fill) ───────────────────────────
export function BandRing({ score, size = 30, stroke = 4 }: { score: number; size?: number; stroke?: number }) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const frac = BAND_FILL[toBand(score)];
  const col = ringColor(score);
  return (
    <svg width={size} height={size} aria-hidden="true" style={{ transform: 'rotate(-90deg)' }} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={col} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={`${(circ * frac).toFixed(1)} ${(circ * (1 - frac)).toFixed(1)}`} />
    </svg>
  );
}

// ── Half-circle gauge (DMMI mood) ────────────────────────────────────────────
export function Semicircle({ val, size = 200 }: { val: number; size?: number }) {
  const stroke = 14;
  const r = (size - stroke) / 2;
  const circ = Math.PI * r;
  const off = circ * (1 - val / 100);
  const col = val >= 70 ? '#00B386' : val >= 55 ? '#F5A623' : val >= 40 ? '#F97316' : '#E5484D';
  const path = `M ${stroke / 2} 0 A ${r} ${r} 0 0 1 ${size - stroke / 2} 0`;
  return (
    <svg width={size} height={size / 2 + 24} viewBox={`0 0 ${size} ${size / 2 + 24}`} className="mx-auto block" aria-hidden="true">
      <g transform={`translate(0,${size / 2})`}>
        <path d={path} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} strokeLinecap="round" />
        <path d={path} fill="none" stroke={col} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={circ.toFixed(1)} strokeDashoffset={off.toFixed(1)} />
        <text x={size / 2} y={-9} textAnchor="middle" fontFamily="var(--font-geist-sans, sans-serif)" fontSize="32" fontWeight="800" fill={col}>{val}</text>
        <text x={size / 2} y={8} textAnchor="middle" fontSize="10" fill="var(--text-muted)" fontFamily="var(--font-geist-mono, monospace)">band</text>
      </g>
    </svg>
  );
}

// ── Tiny sparkline (inline, table / rail) ────────────────────────────────────
function lcg(seed: number) {
  let s = seed;
  return () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
}
export function MiniSpark({ seed, up = true, w = 40, h = 16 }: { seed: number; up?: boolean; w?: number; h?: number }) {
  const N = 20;
  const rnd = lcg(seed);
  const data: number[] = [];
  let v = 50;
  for (let i = 0; i < N; i++) { v += (rnd() - 0.5) * 4 + (up ? 0.4 : -0.3); data.push(v); }
  const lo = Math.min(...data), hi = Math.max(...data), rng = hi - lo || 1;
  const pts = data.map((val, i) => [(i / (N - 1)) * w, h - ((val - lo) / rng) * (h - 2) - 1]);
  const d = 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
  return (
    <svg width={w} height={h} aria-hidden="true" className="inline-block align-middle shrink-0">
      <path d={d} fill="none" stroke={up ? '#00B386' : '#E5484D'} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

// ── Educational label pill (replaces advisory verdict) ───────────────────────
export function EduPill({ word, color }: { word: string; color: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono text-[10px] font-bold whitespace-nowrap" style={{ background: `${color}1A`, color }}>
      {word}
    </span>
  );
}
export function RiskBadge({ risk }: { risk: string }) {
  return <span className="text-[10.5px] font-bold whitespace-nowrap" style={{ color: riskColor(risk) }}>{risk}</span>;
}

// ── Card primitives ──────────────────────────────────────────────────────────
export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('rounded-2xl border border-line bg-surface shadow-sm', className)}>{children}</div>;
}

// "So what" insight strip
export function SoWhat({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3.5 flex gap-2.5 rounded-xl bg-royal/[0.06] px-3.5 py-3 text-small leading-relaxed text-ink-secondary">
      <span className="shrink-0 font-bold text-royal" aria-hidden="true">→</span>
      <p className="m-0">{children}</p>
    </div>
  );
}

// Bold-aware text (renders **bold** spans)
export function RichText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith('**') && p.endsWith('**') ? <b key={i} className="font-semibold text-ink">{p.slice(2, -2)}</b> : <React.Fragment key={i}>{p}</React.Fragment>,
      )}
    </>
  );
}

// Horizontal scroll rail track (edge-to-edge, hidden scrollbar)
export function HScroll({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('-mx-1 flex gap-3 overflow-x-auto px-1 pb-1.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden', className)} style={{ scrollSnapType: 'x proximity' }}>
      {children}
    </div>
  );
}

// Icon button (compare / watch)
export function IconBtn({ title, children, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      className="grid h-7 w-7 place-items-center rounded-md border border-line bg-surface-2 text-ink-secondary transition-colors hover:border-royal hover:text-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      {...rest}
    >
      {children}
    </button>
  );
}

// CTA chip (educational only)
export function CTA({ children, variant = 'ghost', className, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'navy' | 'ghost' }) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-xl px-3.5 py-2 text-small font-semibold transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 whitespace-nowrap',
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

// ── Discovery shortcut card ──────────────────────────────────────────────────
export function DiscCard({ icon, name, count, color }: { icon: string; name: string; count?: string; color: string }) {
  return (
    <button
      type="button"
      className="group cursor-pointer rounded-xl border border-line bg-surface p-4 text-center shadow-sm transition-all hover:-translate-y-0.5 hover:border-royal hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
    >
      <span className="mx-auto mb-2.5 grid h-11 w-11 place-items-center rounded-xl text-xl" style={{ background: `${color}1A`, color }} aria-hidden="true">{icon}</span>
      <span className="block text-small font-bold leading-tight text-ink">{name}</span>
      {count && <span className="mt-0.5 block text-caption text-ink-muted">{count}</span>}
    </button>
  );
}

// ── Mini-leaderboard rail card ───────────────────────────────────────────────
import type { Rail } from './sampleData';
export function MiniLbCard({ rail, width = 280, spark = true }: { rail: Rail; width?: number; spark?: boolean }) {
  return (
    <div className="shrink-0 overflow-hidden rounded-xl border border-line bg-surface shadow-sm" style={{ width, scrollSnapAlign: 'start' }}>
      <div className="flex items-center gap-2.5 border-b border-line px-4 py-3">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-[15px]" style={{ background: `${rail.color}1A`, color: rail.color }} aria-hidden="true">{rail.icon}</span>
        <div className="min-w-0">
          <div className="truncate text-small font-bold leading-tight text-ink">{rail.title}</div>
          <div className="truncate text-caption text-ink-muted">{rail.q}</div>
        </div>
      </div>
      {rail.rows.map((r, i) => (
        <div key={i} className="flex items-center gap-2.5 border-b border-line px-4 py-2.5 last:border-b-0">
          <span className="w-4 shrink-0 font-sans text-xs font-extrabold text-ink-faint">{i + 1}</span>
          <Logo letter={r.logo} color={r.color} size={26} radius={7} font={10} />
          <span className="min-w-0 flex-1 truncate text-[11.5px] font-semibold text-ink">{r.name}</span>
          {spark && <MiniSpark seed={r.name.charCodeAt(0) * 3} up={r.up !== false} />}
          <span className="shrink-0 font-mono text-xs font-extrabold" style={{ color: rail.color }}>{r.val}</span>
        </div>
      ))}
    </div>
  );
}

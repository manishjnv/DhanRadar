/**
 * Fund Detail V3 — shared presentational primitives.
 *
 * Pure UI building blocks ported from the approved V3 mockup into Geist/warm
 * Tailwind tokens. Compliance-critical bits (HeroRing, StrengthBar) render
 * BANDS/WORDS only — never a numeric score (non-neg #2). Charts are deterministic
 * (seeded) so SSR and client markup match.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import type { Strength, Band3 } from './sampleData';

// ───────────────────────────────────────────────────────────────────────────
// tone → text colour
// ───────────────────────────────────────────────────────────────────────────
export const TONE_TEXT: Record<string, string> = {
  emerald: 'text-emerald',
  red: 'text-red',
  amber: 'text-amber',
  cyan: 'text-cyan',
  royal: 'text-royal',
  ink: 'text-ink',
};

// ───────────────────────────────────────────────────────────────────────────
// Preview badge — marks sections fed by illustrative sample data
// ───────────────────────────────────────────────────────────────────────────
export function PreviewBadge({ className }: { className?: string }) {
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

// ───────────────────────────────────────────────────────────────────────────
// "What this means for you" insight line
// ───────────────────────────────────────────────────────────────────────────
export function WhatThisMeans({ children, label = 'What this means for you:' }: { children: React.ReactNode; label?: string }) {
  return (
    <div className="mt-3.5 flex gap-2.5 rounded-xl bg-royal/[0.06] px-3.5 py-3 text-small leading-relaxed text-ink-secondary">
      <span className="shrink-0 font-bold text-royal" aria-hidden="true">→</span>
      <p className="m-0">
        <b className="font-semibold text-ink">{label}</b> {children}
      </p>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Plain card + pad
// ───────────────────────────────────────────────────────────────────────────
export function Panel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <section className={cn('rounded-2xl border border-line bg-surface shadow-sm', className)}>
      {children}
    </section>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Info-tip "i" bubble (KPI snapshot / advanced risk)
// ───────────────────────────────────────────────────────────────────────────
export function InfoTip({ tip }: { tip: string }) {
  return (
    <button
      type="button"
      title={tip}
      aria-label={tip}
      className="inline-grid h-3.5 w-3.5 cursor-help place-items-center rounded-full bg-surface-3 text-[9px] font-bold text-ink-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
    >
      i
    </button>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// HeroRing — COMPLIANCE: label-coloured ring, band-driven fill, NO number.
// ───────────────────────────────────────────────────────────────────────────
const BAND_FILL: Record<'high' | 'medium' | 'low', number> = { high: 0.85, medium: 0.55, low: 0.3 };

export function HeroRing({
  color,
  band,
  size = 118,
  stroke = 10,
  onDark = true,
  centerTop,
  centerWord,
}: {
  color: string;
  band: 'high' | 'medium' | 'low' | null | undefined;
  size?: number;
  stroke?: number;
  onDark?: boolean;
  centerTop?: React.ReactNode;
  centerWord?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const frac = band ? BAND_FILL[band] : null;
  const track = onDark ? 'rgba(255,255,255,.16)' : 'var(--border)';
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" focusable="false">
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
          {frac !== null ? (
            <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={`${circ * frac} ${circ * (1 - frac)}`} />
          ) : (
            <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeDasharray="4 6" opacity={0.6} />
          )}
        </g>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {centerTop}
        {centerWord}
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// StrengthBar — factor row with a strength WORD (no number). Light or dark.
// ───────────────────────────────────────────────────────────────────────────
const STRENGTH_FILL: Record<Strength, number> = { strong: 92, good: 74, moderate: 55, soft: 34 };
const STRENGTH_COLOR: Record<Strength, string> = { strong: '#00B386', good: '#00C2FF', moderate: '#F5A623', soft: '#E5484D' };
const STRENGTH_WORD: Record<Strength, string> = { strong: 'Strong', good: 'Good', moderate: 'Moderate', soft: 'Soft' };

export function StrengthBar({ name, strength, onDark = false }: { name: string; strength: Strength; onDark?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-caption">
      <span className={cn('w-[84px] shrink-0', onDark ? 'text-white/75' : 'text-ink-muted')}>{name}</span>
      <span className={cn('h-[5px] flex-1 overflow-hidden rounded', onDark ? 'bg-white/15' : 'bg-surface-2')}>
        <span className="block h-full rounded" style={{ width: `${STRENGTH_FILL[strength]}%`, background: STRENGTH_COLOR[strength] }} />
      </span>
      <span className={cn('w-[58px] text-right font-mono font-semibold', onDark ? 'text-white' : 'text-ink-secondary')}>
        {STRENGTH_WORD[strength]}
      </span>
    </div>
  );
}

// Decorative band bar (advanced risk / amc quality) — no number.
const BAND_FILL_PCT: Record<Band3, number> = { high: 92, medium: 62, low: 34 };
const BAND_COLOR: Record<Band3, string> = { high: '#00B386', medium: '#F5A623', low: '#64748B' };
export function BandBar({ band, width = 70 }: { band: Band3; width?: number }) {
  return (
    <span className="inline-block h-[5px] overflow-hidden rounded bg-surface-2 align-middle" style={{ width }}>
      <span className="block h-full rounded" style={{ width: `${BAND_FILL_PCT[band]}%`, background: BAND_COLOR[band] }} />
    </span>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Tabs — controlled pill tab-bar
// ───────────────────────────────────────────────────────────────────────────
export function TabBar({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string }[];
  active: string;
  onChange: (k: string) => void;
}) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto rounded-xl bg-surface-2 p-1">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={active === t.key}
          onClick={() => onChange(t.key)}
          className={cn(
            'shrink-0 whitespace-nowrap rounded-lg px-3.5 py-2 text-small font-semibold transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
            active === t.key ? 'bg-surface text-ink shadow-sm' : 'text-ink-muted hover:text-ink',
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// Small chip toggle row (SIP amounts, flow ranges, chart ranges)
export function ChipToggle({
  options,
  active,
  onChange,
  dark = false,
}: {
  options: { key: string; label: string }[];
  active: string;
  onChange: (k: string) => void;
  dark?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          aria-pressed={active === o.key}
          className={cn(
            'rounded-lg border px-3 py-1.5 font-mono text-caption font-semibold transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
            active === o.key
              ? 'border-navy bg-navy text-white'
              : 'border-line bg-surface text-ink-muted hover:text-ink',
          )}
          style={active === o.key ? { background: 'var(--dr-navy,#0B1F3A)', borderColor: 'var(--dr-navy,#0B1F3A)' } : undefined}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Accordion — single collapsible
// ───────────────────────────────────────────────────────────────────────────
export function Accordion({ title, children, defaultOpen = false }: { title: React.ReactNode; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div className="mt-3.5 overflow-hidden rounded-2xl border border-line">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between bg-surface-2 px-4.5 py-3.5 text-small font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
        style={{ paddingLeft: 18, paddingRight: 18 }}
      >
        {title}
        <span className={cn('text-ink-muted transition-transform', open && 'rotate-180')} aria-hidden="true">▾</span>
      </button>
      {open && <div className="px-4.5 py-4" style={{ paddingLeft: 18, paddingRight: 18 }}>{children}</div>}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Deterministic SVG charts (seeded — stable across SSR/client)
// ───────────────────────────────────────────────────────────────────────────
function lcg(seed: number) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

/** Growth-of-₹10k area + benchmark/category comparison lines. */
export function GrowthChart({ seed = 42, height = 170 }: { seed?: number; height?: number }) {
  const W = 640;
  const mk = (s: number, trend: number, vol: number) => {
    const rnd = lcg(s);
    const out: number[] = [];
    let v = 100;
    for (let i = 0; i < 70; i++) { v *= 1 + (rnd() - 0.5) * vol + trend; out.push(v); }
    return out;
  };
  const fund = mk(seed, 0.011, 0.032), cat = mk(seed + 5, 0.0085, 0.03), bench = mk(seed + 9, 0.0105, 0.031);
  const all = [...fund, ...cat, ...bench];
  const lo = Math.min(...all), hi = Math.max(...all), rng = hi - lo || 1;
  const pts = (arr: number[]) => arr.map((v, i) => [(i / (arr.length - 1)) * W, height - ((v - lo) / rng) * (height - 12) - 6]);
  const path = (arr: number[]) => 'M' + pts(arr).map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
  const fp = pts(fund), last = fp[fp.length - 1];
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" className="block">
      <defs>
        <linearGradient id={`fg${seed}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1E5EFF" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#1E5EFF" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${path(fund)} L ${W},${height} L 0,${height} Z`} fill={`url(#fg${seed})`} />
      <path d={path(bench)} fill="none" stroke="#CBD5E1" strokeWidth="1.6" />
      <path d={path(cat)} fill="none" stroke="#F5A623" strokeWidth="1.6" />
      <path d={path(fund)} fill="none" stroke="#1E5EFF" strokeWidth="2.4" />
      <circle cx={last[0].toFixed(1)} cy={last[1].toFixed(1)} r="4" fill="#1E5EFF" />
    </svg>
  );
}

/** Rank trend (lower rank = higher line). */
export function RankChart({ series, height = 150 }: { series: number[]; height?: number }) {
  const W = 640, maxR = 8;
  const pts = series.map((v, i) => [(i / (series.length - 1)) * W, ((v - 1) / (maxR - 1)) * (height - 16) + 8]);
  const path = 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" className="block rounded-xl border border-line" style={{ background: 'linear-gradient(180deg,#F0FDF4,#fff)' }}>
      <path d={path} fill="none" stroke="#00B386" strokeWidth="2.4" />
      {pts.map(([x, y], i) => <circle key={i} cx={x.toFixed(1)} cy={y.toFixed(1)} r="3" fill="#00B386" />)}
      <text x="6" y="14" fontFamily="var(--font-mono,monospace)" fontSize="10" fill="#94A3B8">#1 (best)</text>
      <text x="6" y={height - 6} fontFamily="var(--font-mono,monospace)" fontSize="10" fill="#94A3B8">#8</text>
    </svg>
  );
}

/** Drawdown area (always ≤ 0). */
export function DrawdownChart({ seed = 7, height = 150 }: { seed?: number; height?: number }) {
  const W = 640;
  const rnd = lcg(seed);
  const data: number[] = [];
  let dd = 0;
  for (let i = 0; i < 70; i++) {
    const shock = rnd();
    if (shock > 0.82) dd -= rnd() * 9; else dd += rnd() * 3.4;
    if (dd > 0) dd = 0;
    if (dd < -27) dd = -27;
    data.push(dd);
  }
  const pts = data.map((v, i) => [(i / (data.length - 1)) * W, (-v / 27) * (height - 10) + 5]);
  const path = 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" className="block rounded-xl border border-line" style={{ background: '#FEF2F2' }}>
      <defs>
        <linearGradient id="ddg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#E5484D" stopOpacity="0" />
          <stop offset="100%" stopColor="#E5484D" stopOpacity="0.22" />
        </linearGradient>
      </defs>
      <path d={`${path} L ${W},0 L 0,0 Z`} fill="url(#ddg)" />
      <path d={path} fill="none" stroke="#E5484D" strokeWidth="2" />
    </svg>
  );
}

/** Monthly net-flow bars (signed). */
export function FlowBars({ series, height = 120 }: { series: number[]; height?: number }) {
  const W = 620, n = series.length;
  const max = Math.max(...series.map(Math.abs)) || 1;
  const gap = W / n, bw = gap * 0.6;
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" className="block">
      {series.map((v, i) => {
        const bh = (Math.abs(v) / max) * (height / 2 - 8);
        const x = i * gap + gap * 0.2;
        const y = v >= 0 ? height / 2 - bh : height / 2;
        return <rect key={i} x={x.toFixed(1)} y={y.toFixed(1)} width={bw.toFixed(1)} height={bh.toFixed(1)} rx="2" fill={v >= 0 ? '#00B386' : '#E5484D'} />;
      })}
      <line x1="0" y1={height / 2} x2={W} y2={height / 2} stroke="#CBD5E1" strokeWidth="1" strokeDasharray="3 3" />
    </svg>
  );
}

/** Tiny sparkline for score cards. */
export function Sparkline({ seed, up }: { seed: number; up: boolean }) {
  const N = 20;
  const rnd = lcg(seed);
  const d: number[] = [];
  let v = 50;
  for (let i = 0; i < N; i++) { v += (rnd() - 0.5) * 5 + (up ? 0.5 : -0.4); d.push(v); }
  const lo = Math.min(...d), hi = Math.max(...d), rng = hi - lo || 1;
  const pts = d.map((val, i) => [(i / (N - 1)) * 120, 28 - ((val - lo) / rng) * 24 - 2]);
  const path = 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
  const col = up ? '#00B386' : '#E5484D';
  return (
    <svg width="100%" height="30" viewBox="0 0 120 30" preserveAspectRatio="none" className="block">
      <path d={`${path} L 120,30 L 0,30 Z`} fill={col} opacity="0.12" />
      <path d={path} fill="none" stroke={col} strokeWidth="1.6" />
    </svg>
  );
}

/** Horizontal stacked allocation bar (sectors / cap / asset). */
export function StackBar({ items }: { items: { wt: number; color: string }[] }) {
  return (
    <div className="mb-3.5 flex h-3.5 overflow-hidden rounded-full">
      {items.map((it, i) => <div key={i} style={{ width: `${it.wt}%`, background: it.color }} />)}
    </div>
  );
}

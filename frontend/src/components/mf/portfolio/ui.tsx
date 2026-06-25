/**
 * Portfolio Command Center — shared presentational primitives.
 *
 * Ported 1:1 from the approved PortfolioPageV1 mockup into Geist/warm Tailwind
 * tokens. Responsive by construction — grids collapse on small screens, tables
 * scroll inside their card, so there is no page-level horizontal scroll.
 *
 * COMPLIANCE BRIDGE: score rings render a BAND fill with no inner number, and
 * quality columns render strength WORDS — never a raw DhanRadar 0–100 score
 * (non-neg #2). Status pills use educational labels (non-neg #1).
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

// ── Half-circle gauge (DMMI — market index, DOM value allowed) ───────────────
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

// ── Allocation donut chart ────────────────────────────────────────────────────
// data: [name, pct, color][] — zero-pct rows are filtered before rendering
export function Donut({ data, size = 180, thick = 26 }: { data: [string, number, string][]; size?: number; thick?: number }) {
  const cx = size / 2;
  const cy = size / 2;
  const r = (size - thick) / 2;
  const total = data.reduce((s, [, p]) => s + p, 0) || 1;
  const nonZero = data.filter(([, p]) => p > 0);
  let acc = 0;
  const GAP = 0.018; // radians gap between segments

  const arcs = nonZero.map(([name, pct, col]) => {
    const start = (acc / total) * 2 * Math.PI - Math.PI / 2 + GAP / 2;
    acc += pct;
    const end = (acc / total) * 2 * Math.PI - Math.PI / 2 - GAP / 2;
    const large = end - start > Math.PI ? 1 : 0;
    const x1 = cx + Math.cos(start) * r;
    const y1 = cy + Math.sin(start) * r;
    const x2 = cx + Math.cos(end) * r;
    const y2 = cy + Math.sin(end) * r;
    const d = `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
    return { name, pct, col, d };
  });

  return (
    <svg width={size} height={size} aria-hidden="true" className="shrink-0">
      {arcs.map((a) => (
        <path key={a.name} d={a.d} fill="none" stroke={a.col} strokeWidth={thick} strokeLinecap="butt">
          <title>{a.name}: {a.pct}%</title>
        </path>
      ))}
    </svg>
  );
}

// ── Area chart (deterministic seeded — no network calls) ─────────────────────
function lcg(seed: number) {
  let s = seed;
  return () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
}
export function AreaChart({ seed, width = 520, height = 200, color }: { seed: number; width?: number; height?: number; color: string }) {
  const N = 70;
  const rnd = lcg(seed);
  const pts: number[] = [];
  let v = 100;
  for (let i = 0; i < N; i++) {
    v *= 1 + (rnd() - 0.5) * 0.03 + 0.007;
    pts.push(v);
  }
  const lo = Math.min(...pts);
  const hi = Math.max(...pts);
  const rng = hi - lo || 1;
  const pad = { t: 12, b: 12, l: 8, r: 8 };
  const W = width - pad.l - pad.r;
  const H = height - pad.t - pad.b;
  const coords = pts.map((val, i) => [
    pad.l + (i / (N - 1)) * W,
    pad.t + H - ((val - lo) / rng) * H,
  ]);
  const line = 'M' + coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
  const area = line + ` L${coords[coords.length - 1][0].toFixed(1)},${(pad.t + H).toFixed(1)} L${coords[0][0].toFixed(1)},${(pad.t + H).toFixed(1)} Z`;
  const gradId = `ag-${seed}`;
  const last = coords[coords.length - 1];

  return (
    <svg width={width} height={height} aria-hidden="true" className="w-full">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradId})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r={4} fill={color} />
    </svg>
  );
}

// ── Card wrapper ─────────────────────────────────────────────────────────────
export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('rounded-2xl border border-line bg-surface shadow-sm', className)}>{children}</div>;
}

// ── "So what" insight strip ──────────────────────────────────────────────────
export function SoWhat({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3.5 flex gap-2.5 rounded-xl bg-royal/[0.06] px-3.5 py-3 text-small leading-relaxed text-ink-secondary">
      <span className="shrink-0 font-bold text-royal" aria-hidden="true">→</span>
      <p className="m-0">{children}</p>
    </div>
  );
}

// ── RichText — renders **bold** spans ────────────────────────────────────────
export function RichText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith('**') && p.endsWith('**')
          ? <b key={i} className="font-semibold text-ink">{p.slice(2, -2)}</b>
          : <React.Fragment key={i}>{p}</React.Fragment>,
      )}
    </>
  );
}

// ── StatusTag — educational label pill ───────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  'In Form': '#00B386',
  'On Track': '#1E5EFF',
  'Off Track': '#E5484D',
  'Out of Form': '#E5484D',
};
export function StatusTag({ status }: { status: string }) {
  const col = STATUS_COLORS[status] ?? '#F5A623';
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono text-[10px] font-bold whitespace-nowrap"
      style={{ background: `${col}1A`, color: col }}
    >
      {status}
    </span>
  );
}

// ── RiskBadge ────────────────────────────────────────────────────────────────
export function RiskBadge({ risk }: { risk: string }) {
  return <span className="text-[10.5px] font-bold whitespace-nowrap" style={{ color: riskColor(risk) }}>{risk}</span>;
}

// ── CTA button ───────────────────────────────────────────────────────────────
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

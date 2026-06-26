/**
 * Calculator Hub V1 — shared presentational primitives.
 *
 * Ported 1:1 from the approved CalculatorHubV1 desktop + mobile mockups into
 * Geist/warm Tailwind tokens. Responsive by construction: card grids collapse
 * to a single column on small screens, the featured / learn / related rows
 * become horizontal-scroll rails on mobile (the dedicated mobile layout) and
 * grids from `sm:` up.
 *
 * PURE UI: sliders/toggles are inert placeholders, charts render fixed preview
 * seed data, no value is a DhanRadar-computed fund score. The calculator engine,
 * search, and filtering are wired in a later session.
 */
'use client';

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { formatInrShort } from '@/lib/finance';
import {
  type Accent,
  type Featured,
  type Category,
  type CalcMini,
  accentTile,
  ACCENT_HEX,
  TAG_ACCENT,
} from './data';

// ── Icon tile ────────────────────────────────────────────────────────────────
export function IconTile({
  emoji,
  accent,
  className,
  style,
}: {
  emoji: string;
  accent: Accent;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={cn('grid place-items-center rounded-xl', className)}
      style={{ ...accentTile(accent), ...style }}
      aria-hidden="true"
    >
      {emoji}
    </div>
  );
}

// ── Arrow / chevron glyphs (lucide-style inline) ─────────────────────────────
export function ArrowRight({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}
export function ChevronRight({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}
export function ChevronDown({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M6 9 L12 15 L18 9" />
    </svg>
  );
}
export function SearchIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="M16 16 L21 21" />
    </svg>
  );
}
export function SparkIcon({ size = 17 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3 L13.5 9 L19 10.5 L13.5 12 L12 18 L10.5 12 L5 10.5 L10.5 9 Z" />
    </svg>
  );
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

// Bold-aware text (renders **bold** spans)
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
  return <div className={cn('rounded-2xl border border-line bg-surface p-5 shadow-sm', className)}>{children}</div>;
}

// ── Buttons ──────────────────────────────────────────────────────────────────
type BtnVariant = 'pri' | 'ghost';
export function Btn({
  children,
  variant = 'ghost',
  className,
  onClick,
  type = 'button',
  'aria-label': ariaLabel,
}: {
  children: React.ReactNode;
  variant?: BtnVariant;
  className?: string;
  onClick?: () => void;
  type?: 'button' | 'submit';
  'aria-label'?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      aria-label={ariaLabel}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-[10px] border px-3.5 py-2.5 text-small font-semibold transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
        variant === 'pri'
          ? 'border-transparent bg-royal text-white hover:bg-royal/90'
          : 'border-line bg-surface-2 text-ink hover:bg-surface-3',
        className,
      )}
    >
      {children}
    </button>
  );
}

// ── Hero (hub) ───────────────────────────────────────────────────────────────
export function Hero({
  title,
  subtitle,
  searchPlaceholder,
  cats,
  stats,
  searchValue = '',
  onSearchChange,
  onSearchSubmit,
  onSelectCat,
  activeCat,
}: {
  title: string;
  subtitle: string;
  searchPlaceholder: string;
  cats: { emoji: string; label: string }[];
  stats: { label: string; value: string; small?: boolean }[];
  searchValue?: string;
  onSearchChange?: (v: string) => void;
  onSearchSubmit?: () => void;
  onSelectCat?: (label: string) => void;
  activeCat?: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-navy via-[#16335E] to-royal p-6 text-white shadow-[0_24px_60px_-20px_rgba(15,23,42,.45)] sm:p-8">
      {/* decorative glow */}
      <span aria-hidden="true" className="pointer-events-none absolute -right-12 -top-16 h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(37,99,235,.4),transparent_70%)]" />
      <span aria-hidden="true" className="pointer-events-none absolute -bottom-32 left-1/3 h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(16,185,129,.2),transparent_70%)]" />
      <div className="relative z-[2]">
        <h1 className="m-0 text-[clamp(26px,5vw,34px)] font-medium leading-[1.05] tracking-[-0.03em]">{title}</h1>
        <p className="mb-5 mt-2 max-w-xl text-body leading-snug text-slate-300">{subtitle}</p>

        {/* Search */}
        <form
          className="relative max-w-xl"
          onSubmit={(e) => { e.preventDefault(); onSearchSubmit?.(); }}
          role="search"
        >
          <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-muted"><SearchIcon /></span>
          <input
            type="search"
            aria-label="Search calculators"
            placeholder={searchPlaceholder}
            value={searchValue}
            onChange={(e) => onSearchChange?.(e.target.value)}
            className="h-[52px] w-full rounded-[14px] border-none bg-white/95 pl-12 pr-4 text-body text-ink shadow-sm outline-none placeholder:text-ink-muted focus-visible:ring-2 focus-visible:ring-royal"
          />
        </form>

        {/* Quick category chips */}
        <div className="mt-4 flex flex-wrap gap-2">
          {cats.map((c) => {
            const isActive = activeCat === c.label;
            return (
              <button
                key={c.label}
                type="button"
                onClick={() => onSelectCat?.(c.label)}
                aria-pressed={isActive}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-[11px] border px-3.5 py-2 text-small font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50',
                  isActive
                    ? 'border-white bg-white text-navy'
                    : 'border-white/20 bg-white/10 text-white hover:bg-white/20',
                )}
              >
                <span aria-hidden="true">{c.emoji}</span> {c.label}
              </button>
            );
          })}
        </div>

        {/* Stat strip */}
        <div className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-[13px] bg-white/10 sm:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="bg-white/[0.04] px-4 py-3">
              <div className="text-[9.5px] font-semibold uppercase tracking-[0.04em] text-slate-400">{s.label}</div>
              <div className={cn('mt-1 font-medium', s.small ? 'text-[15px]' : 'text-[20px]')}>{s.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Horizontal-scroll rail (mobile) → grid (sm+) ─────────────────────────────
export function Rail({ children, gridCols, className }: { children: React.ReactNode; gridCols: string; className?: string }) {
  return (
    <div
      className={cn(
        'flex gap-3 overflow-x-auto pb-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden',
        'sm:grid sm:gap-3 sm:overflow-visible',
        gridCols,
        className,
      )}
    >
      {children}
    </div>
  );
}

// ── Featured card ────────────────────────────────────────────────────────────
export function FeatureCard({ item, href, live }: { item: Featured; href: string; live?: boolean }) {
  const tagHex = ACCENT_HEX[TAG_ACCENT[item.tag]];
  return (
    <Link
      href={href}
      className="group relative block w-[200px] shrink-0 rounded-[15px] border border-line bg-surface p-4 text-left shadow-sm transition-all hover:-translate-y-[3px] hover:border-royal hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 sm:w-auto"
    >
      <span
        className="absolute right-3 top-3 rounded-md px-1.5 py-[3px] font-mono text-[8.5px] font-bold uppercase tracking-[0.03em]"
        style={{ background: `${tagHex}1A`, color: tagHex }}
      >
        {item.tag}
      </span>
      <IconTile emoji={item.emoji} accent={item.accent} className="mb-3 h-[46px] w-[46px] text-[21px]" />
      <div className="text-small font-semibold leading-tight text-ink">{item.name}</div>
      <div className="mt-1.5 text-caption leading-snug tracking-normal text-ink-muted">{item.desc}</div>
      <div className="mt-3 flex items-center gap-2 text-caption font-semibold tracking-normal">
        {live && (
          <span className="inline-flex items-center gap-1 rounded text-emerald">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald" aria-hidden="true" />Live
          </span>
        )}
        <span className="inline-flex items-center gap-1.5 text-royal">Open <ArrowRight /></span>
      </div>
    </Link>
  );
}

// ── Category card ────────────────────────────────────────────────────────────
export function CategoryCard({ item, count, onSelect }: { item: Category; count: number; onSelect: (name: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(item.name)}
      className="flex items-center gap-3 rounded-[15px] border border-line bg-surface p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
    >
      <IconTile emoji={item.emoji} accent={item.accent} className="h-[46px] w-[46px] shrink-0 text-[20px]" />
      <div>
        <div className="text-small font-semibold text-ink">{item.name}</div>
        <div className="mt-0.5 text-caption tracking-normal text-ink-muted">{count} calculator{count === 1 ? '' : 's'}</div>
      </div>
    </button>
  );
}

// ── Calculator mini card ─────────────────────────────────────────────────────
export function CalcMiniCard({ item, href, live }: { item: CalcMini; href: string; live?: boolean }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 rounded-xl border border-line bg-surface p-3 text-left transition-colors hover:border-royal hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
    >
      <IconTile emoji={item.emoji} accent={item.accent} className="h-9 w-9 shrink-0 text-[16px]" />
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-small font-semibold leading-tight text-ink">{item.name}</span>
          {live && (
            <span className="inline-flex shrink-0 items-center gap-1 rounded bg-emerald/15 px-1.5 py-0.5 font-mono text-[8.5px] font-bold uppercase tracking-[0.03em] text-emerald">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald" aria-hidden="true" />Live
            </span>
          )}
        </div>
        <div className="mt-px text-caption tracking-normal text-ink-muted">{item.category}</div>
      </div>
      <span className="ml-auto shrink-0 text-ink-faint"><ChevronRight /></span>
    </Link>
  );
}

// ── Filter chips — controlled when `active`/`onSelect` are passed ─────────────
export function ChipRow({ chips, scroll = false, active, onSelect }: { chips: string[]; scroll?: boolean; active?: string; onSelect?: (chip: string) => void }) {
  const [internal, setInternal] = React.useState(chips[0] ?? '');
  const current = active ?? internal;
  const select = (c: string) => { setInternal(c); onSelect?.(c); };
  return (
    <div
      className={cn(
        'flex gap-2',
        scroll
          ? 'overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:flex-wrap sm:overflow-visible'
          : 'flex-wrap',
      )}
    >
      {chips.map((c) => (
        <button
          key={c}
          type="button"
          onClick={() => select(c)}
          aria-pressed={current === c}
          className={cn(
            'shrink-0 rounded-[10px] border px-3.5 py-2 text-small font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
            current === c
              ? 'border-navy bg-navy text-white'
              : 'border-line bg-surface text-ink-secondary shadow-sm hover:border-royal hover:text-royal',
          )}
        >
          {c}
        </button>
      ))}
    </div>
  );
}

// ── Learn card ───────────────────────────────────────────────────────────────
export function LearnCard({ emoji, q, a }: { emoji: string; q: string; a: string }) {
  return (
    <div className="w-[220px] shrink-0 rounded-[13px] border border-line bg-surface p-3.5 sm:w-auto">
      <div className="flex items-center gap-1.5 text-small font-semibold text-ink"><span aria-hidden="true">{emoji}</span> {q}</div>
      <div className="mt-1.5 text-caption leading-snug tracking-normal text-ink-muted">{a}</div>
    </div>
  );
}

// ── FAQ accordion ────────────────────────────────────────────────────────────
export function Faq({ items }: { items: { q: string; a: string }[] }) {
  const [open, setOpen] = React.useState(0);
  return (
    <Panel className="p-0">
      {items.map((it, i) => {
        const isOpen = open === i;
        return (
          <div key={it.q} className={cn('border-b border-line last:border-b-0')}>
            <button
              type="button"
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? -1 : i)}
              className="flex w-full items-center justify-between gap-3 px-4 py-4 text-left text-small font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-royal/40"
            >
              {it.q}
              <span className={cn('shrink-0 text-ink-muted transition-transform', isOpen && 'rotate-180')}><ChevronDown /></span>
            </button>
            {isOpen && (
              <div className="max-w-[880px] px-4 pb-4 text-small leading-relaxed text-ink-muted">{it.a}</div>
            )}
          </div>
        );
      })}
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SIP DETAIL primitives (inert)
// ─────────────────────────────────────────────────────────────────────────────

// Controlled range field — slider + an editable number box + clickable presets.
export function RangeField({
  label,
  tip,
  value,
  min,
  max,
  step = 1,
  format,
  presets,
  onChange,
  unit,
}: {
  label: string;
  tip: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  format: (n: number) => string;
  presets: { label: string; value: number }[];
  onChange: (n: number) => void;
  unit?: '₹' | '%' | 'yrs';
}) {
  // Editable box: type freely while focused; clamp to [min,max] on blur / Enter.
  const [draft, setDraft] = React.useState<string | null>(null);
  const commit = () => {
    if (draft === null) return;
    const v = Number(draft);
    setDraft(null);
    if (Number.isFinite(v)) onChange(Math.min(Math.max(v, min), max));
  };
  return (
    <div className="mb-5">
      <div className="mb-2.5 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-small font-semibold text-ink">
          {label}
          <span title={tip} className="inline-grid h-[15px] w-[15px] cursor-help place-items-center rounded-full bg-surface-3 text-[9px] font-bold text-ink-muted">i</span>
        </span>
        <span className="inline-flex items-center gap-0.5 rounded-[9px] bg-royal/10 px-2 py-1 font-mono text-small font-bold text-royal focus-within:ring-2 focus-within:ring-royal/40">
          {unit === '₹' && <span aria-hidden="true">₹</span>}
          <input
            type="number"
            inputMode="numeric"
            value={draft ?? value}
            min={min}
            max={max}
            step={step}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
            aria-label={`${label} — type a value`}
            className="w-[88px] bg-transparent text-right tabular-nums outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          />
          {unit === '%' && <span aria-hidden="true">%</span>}
          {unit === 'yrs' && <span className="text-caption" aria-hidden="true">yr</span>}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={label}
        className="h-1.5 w-full accent-royal"
      />
      <div className="mt-1.5 flex justify-between font-mono text-[10.5px] text-ink-muted">
        <span>{format(min)}</span>
        <span>{format(max)}</span>
      </div>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {presets.map((p) => {
          const active = value === p.value;
          return (
            <button
              key={p.label}
              type="button"
              onClick={() => onChange(p.value)}
              aria-pressed={active}
              className={cn(
                'rounded-lg border px-2.5 py-1.5 text-caption font-semibold tracking-normal transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                active
                  ? 'border-royal bg-royal text-white'
                  : 'border-line bg-surface-2 text-ink-secondary hover:border-royal hover:text-royal',
              )}
            >
              {p.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// Toggle row — a real switch (controlled via `on` + `onToggle`).
export function ToggleRow({ title, sub, on = false, onToggle }: { title: string; sub: string; on?: boolean; onToggle?: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onToggle}
      className="flex w-full items-center justify-between rounded-xl border border-line bg-surface-2 p-3.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
    >
      <div>
        <div className="text-small font-semibold text-ink">{title}</div>
        <div className="mt-0.5 text-caption tracking-normal text-ink-muted">{sub}</div>
      </div>
      <span
        aria-hidden="true"
        className={cn('relative h-6 w-[42px] shrink-0 rounded-xl transition-colors', on ? 'bg-royal' : 'bg-line-strong')}
      >
        <span className={cn('absolute left-[3px] top-[3px] h-[18px] w-[18px] rounded-full bg-white transition-transform', on && 'translate-x-[18px]')} />
      </span>
    </button>
  );
}

// KPI tile
export function Kpi({ label, value, sub, accent, hero }: { label: string; value: string; sub: string; accent?: 'pos'; hero?: boolean }) {
  if (hero) {
    return (
      <div className="relative col-span-full overflow-hidden rounded-[14px] bg-gradient-to-br from-navy to-royal p-4 text-white">
        <div className="text-caption font-semibold uppercase tracking-[0.04em] text-slate-400">{label}</div>
        <div className="mt-1.5 font-mono text-[38px] font-bold leading-none tracking-[-0.02em]">{value}</div>
        <div className="mt-1 text-caption tracking-normal text-slate-300">{sub}</div>
      </div>
    );
  }
  return (
    <div className="rounded-[14px] border border-line bg-surface p-4">
      <div className="text-caption font-semibold uppercase tracking-[0.04em] text-ink-muted">{label}</div>
      <div className={cn('mt-1.5 font-mono text-[24px] font-bold leading-none tracking-[-0.02em]', accent === 'pos' ? 'text-emerald' : 'text-ink')}>{value}</div>
      <div className="mt-1 text-caption tracking-normal text-ink-muted">{sub}</div>
    </div>
  );
}

// Growth chart with ₹ Y-axis labels, year X-axis labels, and per-point hover
// tooltips (native SVG <title> — hover any year to see invested vs value).
export function GrowthChart({ series }: { series: { year: number; invested: number; value: number }[] }) {
  const W = 600;
  const H = 240;
  const padL = 54;
  const padR = 10;
  const padT = 10;
  const padB = 26;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const n = series.length;
  const maxV = Math.max(...series.map((d) => d.value), 1) * 1.05;
  const xAt = (idx: number) => padL + (n <= 1 ? plotW : (idx / (n - 1)) * plotW);
  const yAt = (v: number) => padT + plotH - (Math.max(v, 0) / maxV) * plotH;
  const toPath = (key: 'value' | 'invested') =>
    'M' + series.map((d, idx) => `${xAt(idx).toFixed(1)},${yAt(d[key]).toFixed(1)}`).join(' L');
  const wd = toPath('value');
  const idd = toPath('invested');
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * maxV);
  const xStep = Math.max(1, Math.ceil((n - 1) / 6));
  const baseY = yAt(0);
  const [hover, setHover] = React.useState<number | null>(null);
  const lastHover = React.useRef(0);
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="block" role="img" aria-label="Money invested versus estimated value by year; hover a point for the figures.">
      <defs>
        <linearGradient id="calc-wg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={ACCENT_HEX.royal} stopOpacity="0.22" />
          <stop offset="100%" stopColor={ACCENT_HEX.royal} stopOpacity="0" />
        </linearGradient>
        <filter id="calc-tip-shadow" x="-20%" y="-30%" width="140%" height="170%">
          <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor={ACCENT_HEX.navy} floodOpacity="0.35" />
        </filter>
      </defs>

      {/* Y gridlines + ₹ labels */}
      {yTicks.map((t, k) => (
        <g key={`y${k}`}>
          <line x1={padL} y1={yAt(t)} x2={W - padR} y2={yAt(t)} stroke="var(--text-faint)" strokeWidth="1" opacity="0.45" />
          <text x={padL - 7} y={yAt(t) + 3} textAnchor="end" fontSize="9" fontFamily="ui-monospace, monospace" fill="var(--text-muted)">{formatInrShort(t)}</text>
        </g>
      ))}

      {/* Areas */}
      <path d={`${idd} L ${xAt(n - 1)},${baseY} L ${padL},${baseY} Z`} fill="var(--surface-3)" opacity="0.5" />
      <path d={`${wd} L ${xAt(n - 1)},${baseY} L ${padL},${baseY} Z`} fill="url(#calc-wg)" />

      {/* Lines */}
      <path d={idd} fill="none" stroke="var(--text-faint)" strokeWidth="2" strokeDasharray="4 3" />
      <path d={wd} fill="none" stroke={ACCENT_HEX.royal} strokeWidth="2.5" />

      {/* X labels + value dots */}
      {series.map((d, idx) => {
        const showLabel = idx % xStep === 0 || idx === n - 1;
        return (
          <g key={`x${idx}`}>
            {showLabel && (
              <text x={xAt(idx)} y={H - 8} textAnchor="middle" fontSize="9" fontFamily="ui-monospace, monospace" fill="var(--text-muted)">{d.year}y</text>
            )}
            {showLabel && <circle cx={xAt(idx)} cy={yAt(d.value)} r="2.6" fill={ACCENT_HEX.royal} />}
          </g>
        );
      })}

      {/* Hover hit-areas — drive the instant tooltip (no native-title delay) */}
      {series.map((d, idx) => (
        <circle
          key={`h${idx}`}
          cx={xAt(idx)}
          cy={yAt(d.value)}
          r="13"
          fill="transparent"
          className="cursor-pointer"
          onMouseEnter={() => { lastHover.current = idx; setHover(idx); }}
          onMouseLeave={() => setHover((h) => (h === idx ? null : h))}
        />
      ))}

      {/* Tooltip — stays mounted and fades in/out smoothly (uses the last point
          while fading out so it doesn't blink between points). */}
      {(() => {
        const idx = hover ?? lastHover.current;
        const d = series[idx];
        if (!d) return null;
        const cx = xAt(idx);
        const cy = yAt(d.value);
        const tw = 158;
        const th = 44;
        const tx = Math.max(padL, Math.min(cx - tw / 2, W - padR - tw));
        const ty = cy - th - 12 < padT ? cy + 14 : cy - th - 12;
        return (
          <g pointerEvents="none" className={cn('transition-opacity duration-200 ease-out', hover !== null ? 'opacity-100' : 'opacity-0')}>
            <line x1={cx} y1={padT} x2={cx} y2={baseY} stroke={ACCENT_HEX.royal} strokeWidth="1" strokeDasharray="3 3" opacity="0.4" />
            <circle cx={cx} cy={cy} r="5" fill={ACCENT_HEX.royal} stroke="#fff" strokeWidth="2" />
            <g transform={`translate(${tx},${ty})`}>
              <rect width={tw} height={th} rx="8" fill={ACCENT_HEX.navy} filter="url(#calc-tip-shadow)" />
              <text x="11" y="18" fill="#fff" fontSize="11" fontWeight="700" fontFamily="ui-monospace, monospace">Year {d.year} · {formatInrShort(d.value)}</text>
              <text x="11" y="33" fill="#cbd5e1" fontSize="9.5" fontFamily="ui-monospace, monospace">Invested {formatInrShort(d.invested)}</text>
            </g>
          </g>
        );
      })()}
    </svg>
  );
}

// Donut (two-slice) with hover — hover a slice to see its label, amount, and %.
export function Donut({
  invested,
  profit,
  labels = ['Invested', 'Profit'],
  size = 150,
  thick = 26,
}: {
  invested: number;
  profit: number;
  labels?: [string, string];
  size?: number;
  thick?: number;
}) {
  const [hover, setHover] = React.useState<number | null>(null);
  const data = [
    { v: Math.max(invested, 0), c: 'var(--surface-3)', label: labels[0] },
    { v: Math.max(profit, 0), c: ACCENT_HEX.royal, label: labels[1] },
  ];
  const r = (size - thick - 4) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const total = data[0].v + data[1].v || 1;
  const active = hover !== null ? data[hover] : null;
  let acc = 0;
  return (
    <svg width={size} height={size} role="img" aria-label={`${labels[0]} versus ${labels[1]}; hover a slice for its amount.`}>
      {data.map((d, i) => {
        const start = (acc / total) * 2 * Math.PI - Math.PI / 2;
        acc += d.v;
        const end = (acc / total) * 2 * Math.PI - Math.PI / 2;
        const large = end - start > Math.PI ? 1 : 0;
        const x1 = cx + Math.cos(start) * r;
        const y1 = cy + Math.sin(start) * r;
        const x2 = cx + Math.cos(end) * r;
        const y2 = cy + Math.sin(end) * r;
        return (
          <path
            key={i}
            d={`M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`}
            fill="none"
            stroke={d.c}
            strokeWidth={hover === i ? thick + 5 : thick}
            opacity={hover === null || hover === i ? 1 : 0.4}
            className="cursor-pointer transition-all duration-150"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover((h) => (h === i ? null : h))}
          />
        );
      })}
      {/* Center detail */}
      {active ? (
        <>
          <text x={cx} y={cy - 9} textAnchor="middle" fontSize="9.5" fontFamily="ui-monospace, monospace" fill="var(--text-muted)">{active.label}</text>
          <text x={cx} y={cy + 7} textAnchor="middle" fontSize="14" fontWeight="700" fill="var(--text-secondary)">{formatInrShort(active.v)}</text>
          <text x={cx} y={cy + 22} textAnchor="middle" fontSize="10" fontFamily="ui-monospace, monospace" fill="var(--text-muted)">{Math.round((active.v / total) * 100)}%</text>
        </>
      ) : (
        <>
          <text x={cx} y={cy - 3} textAnchor="middle" fontSize="9" fontFamily="ui-monospace, monospace" fill="var(--text-muted)">Total</text>
          <text x={cx} y={cy + 13} textAnchor="middle" fontSize="14" fontWeight="700" fill="var(--text-secondary)">{formatInrShort(total)}</text>
        </>
      )}
    </svg>
  );
}

// What-if card
export function WhatIfCard({ name, val, result, delta, up }: { name: string; val: string; result: string; delta: string; up: boolean }) {
  return (
    <div className="rounded-[13px] border border-line p-3.5">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-small font-semibold text-ink">{name}</span>
        <span className="font-mono text-caption font-bold tracking-normal text-royal">{val}</span>
      </div>
      <div className="text-[17px] font-medium text-ink">{result}</div>
      <div className={cn('mt-0.5 text-caption font-semibold tracking-normal', up ? 'text-emerald' : 'text-red')}>{delta}</div>
    </div>
  );
}

// AI insight card
export function AiCard({ text }: { text: string }) {
  return (
    <div className="flex gap-3 rounded-[14px] border border-line bg-gradient-to-br from-[#FAFBFF] to-white p-4">
      <span className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-[10px] bg-royal/10 text-royal"><SparkIcon /></span>
      <p className="m-0 text-small leading-relaxed text-ink-secondary"><RichText text={text} /></p>
    </div>
  );
}

// Related calculator card
export function RelatedCard({ emoji, name, desc, accent, href }: { emoji: string; name: string; desc: string; accent: Accent; href: string }) {
  return (
    <Link
      href={href}
      className="flex w-[170px] shrink-0 items-center gap-3 rounded-xl border border-line bg-surface p-3.5 text-left transition-colors hover:border-royal hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 sm:w-auto"
    >
      <IconTile emoji={emoji} accent={accent} className="h-9 w-9 shrink-0 text-[16px]" />
      <div className="min-w-0">
        <div className="truncate text-small font-semibold text-ink">{name}</div>
        <div className="truncate text-caption tracking-normal text-ink-muted">{desc}</div>
      </div>
    </Link>
  );
}

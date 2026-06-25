/**
 * Watchlist Monitor — section components (desktop + mobile, one responsive tree).
 *
 * Built 1:1 to the approved WatchlistPageV1 desktop + mobile mockups. Multi-col
 * grids collapse to a single column on phones; "rail" sections (What Changed,
 * Best Opportunities, Similar Funds, Recently Viewed) become horizontal
 * scrollers on phones and grids on larger screens — matching the mobile mockup.
 *
 * PURE-UI: every value is illustrative preview data from sampleData.ts. Buttons
 * are visual placeholders; selection + accordion + tab/chip toggles are local
 * view state only (no API, no business logic).
 */
'use client';

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import {
  Logo, BandRing, Semicircle, Donut, Card, SoWhat, RichText, CTA,
  Spark, Pill, Chip, MetricTile, MiniLogo, SoftPill,
} from './ui';
import {
  COLORS, FUNDS, type Fund, HERO, BENEFITS, AI_SUMMARY, INSIGHTS,
  FILTER_CHIPS, SORT_OPTIONS, CHANGED, OPPORTUNITIES, DMMI, PERF_TABS,
  PERF_HEAD, PERF_ROWS, ALERTS, SIMILAR, STATS, CATEGORY_MIX, DISCOVERY,
  RECENTLY_VIEWED, FAQ, FILTER_GROUPS,
  toStrength, STRENGTH_WORD, riskColor, verdictOf, momentumOf, fmtAum, DMMI_COLOR,
} from './sampleData';

const { E, B, A, R, O } = COLORS;

// ── Generic AI-insight card grid (AI Summary + Insights) ─────────────────────
export function AiCardsGrid({ items }: { items: string[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      {items.map((t, i) => (
        <div key={i} className="flex gap-3 rounded-2xl border border-line bg-gradient-to-br from-royal/[0.03] to-surface p-4">
          <span className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-[10px] bg-violet/10 text-violet" aria-hidden="true">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3 L13.5 9 L19 10.5 L13.5 12 L12 18 L10.5 12 L5 10.5 L10.5 9 Z" />
            </svg>
          </span>
          <p className="m-0 text-small leading-relaxed text-ink-secondary"><RichText text={t} /></p>
        </div>
      ))}
    </div>
  );
}

// ── S1 HERO ──────────────────────────────────────────────────────────────────
export function HeroSection({ onCompare }: { onCompare?: () => void }) {
  return (
    <div className="relative overflow-hidden rounded-3xl px-6 py-6 text-white shadow-xl sm:px-7"
      style={{ background: 'linear-gradient(135deg,#0B1F3A 0%,#16335E 60%,#1E40AF 100%)' }}>
      <div className="pointer-events-none absolute -right-12 -top-16 h-72 w-72 rounded-full"
        style={{ background: 'radial-gradient(circle,rgba(37,99,235,.36),transparent 70%)' }} aria-hidden="true" />
      <div className="relative">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-sans text-[24px] font-extrabold tracking-tight">{HERO.title}</h1>
            <div className="mt-1 text-small text-slate-300">{HERO.sub}</div>
          </div>
          <div className="flex flex-wrap gap-2">
            {HERO.actions.map((a) => (
              <button key={a.label} type="button" onClick={a.primary ? onCompare : undefined}
                className={cn(
                  'rounded-xl border px-3 py-2 text-caption font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40 whitespace-nowrap',
                  a.primary ? 'border-white bg-white text-navy hover:bg-white/90' : 'border-white/20 bg-white/10 text-white hover:bg-white/20',
                )}>
                {a.label}
              </button>
            ))}
          </div>
        </div>

        {/* KPIs */}
        <div className="mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-2xl bg-white/10 sm:grid-cols-3 lg:grid-cols-6">
          {HERO.kpis.map((k) => (
            <div key={k.label} className="bg-white/[0.04] px-3.5 py-3">
              <div className="text-[9.5px] font-semibold uppercase leading-tight tracking-wide text-slate-400">{k.label}</div>
              <div className={cn('mt-1 font-sans font-extrabold leading-tight', k.small ? 'text-sm' : 'text-[19px]')}
                style={{ color: k.color }}>
                {k.value}{k.sub && <small className="ml-1 text-[11px] font-semibold opacity-85">{k.sub}</small>}
              </div>
            </div>
          ))}
        </div>

        {/* Summary pills */}
        <div className="mt-4 flex flex-wrap gap-2.5">
          {HERO.summary.map((s, i) => (
            <span key={i} className="inline-flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/10 px-3 py-2 text-caption font-semibold">
              {s.prefix
                ? <>{s.text} <span className="font-mono font-extrabold" style={{ color: s.color }}>{s.n}</span></>
                : <><span className="font-mono font-extrabold" style={{ color: s.color }}>{s.n}</span> {s.text}</>}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── S3 FILTER & SORT ─────────────────────────────────────────────────────────
export function FilterSection() {
  const [active, setActive] = React.useState(0);
  const [sort, setSort] = React.useState('DhanRadar Strength');
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="relative min-w-[200px] flex-1 sm:max-w-[320px]">
          <svg className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <circle cx="11" cy="11" r="7" /><path d="M16 16 L21 21" />
          </svg>
          <input type="search" placeholder="Search watchlist…" aria-label="Search watchlist"
            className="h-10 w-full rounded-xl border border-line-strong bg-surface pl-9 pr-3 text-small text-ink outline-none focus:border-royal focus:ring-2 focus:ring-royal/20" />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {FILTER_CHIPS.map(([label, count], i) => (
            <Chip key={label} label={label} count={count} active={i === active} onClick={() => setActive(i)} />
          ))}
        </div>
        <label className="ml-auto flex items-center gap-2 text-caption text-ink-muted">
          Sort
          <select value={sort} onChange={(e) => setSort(e.target.value)}
            className="cursor-pointer rounded-lg border border-line-strong bg-surface px-2.5 py-2 text-caption font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
            {SORT_OPTIONS.map((o) => <option key={o}>{o}</option>)}
          </select>
        </label>
      </div>
    </Card>
  );
}

// ── S4 FUND CARD + GRID ──────────────────────────────────────────────────────
function FundCard({ fund, index, selected, onToggle }: { fund: Fund; index: number; selected: boolean; onToggle: (i: number) => void }) {
  const [vt, vc] = verdictOf(fund.score);
  const [mtxt, mcol] = momentumOf(fund.status);
  const strength = STRENGTH_WORD[toStrength(fund.score)];
  const sipWord = STRENGTH_WORD[toStrength(fund.sip)];
  return (
    <div className="relative flex flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-sm">
      <button type="button" onClick={() => onToggle(index)} aria-pressed={selected}
        aria-label={selected ? `Remove ${fund.name} from comparison` : `Add ${fund.name} to comparison`}
        className={cn(
          'absolute right-3 top-3 z-[3] grid h-[22px] w-[22px] place-items-center rounded-[7px] border-2 text-xs font-extrabold transition-colors',
          selected ? 'border-royal bg-royal text-white' : 'border-line-strong bg-surface text-transparent',
        )}>
        ✓
      </button>
      <div className="flex-1 p-4">
        <div className="flex items-start gap-3 pr-7">
          <Logo letter={fund.logo} color={fund.color} size={40} radius={11} font={15} />
          <div className="min-w-0">
            <div className="text-[13.5px] font-bold leading-tight text-ink">{fund.name}</div>
            <div className="mt-0.5 text-[11px] text-ink-muted">{fund.amc} · {fund.cat} · {fund.age}y</div>
            <div className="mt-1.5"><Pill label={mtxt} color={mcol} /></div>
          </div>
        </div>

        <div className="mt-3 flex items-end justify-between">
          <div>
            <div className="font-mono text-lg font-extrabold text-ink">₹{fund.nav.toFixed(2)}</div>
            <div className="text-[9.5px] font-semibold uppercase tracking-wide text-ink-muted">NAV</div>
          </div>
          <div className="text-right">
            <div className={cn('font-mono text-xs font-bold', fund.chg >= 0 ? 'text-emerald' : 'text-red')}>
              {fund.chg >= 0 ? '+' : ''}{fund.chg}%
            </div>
            <div className="text-[9.5px] text-ink-muted">today</div>
          </div>
        </div>

        <div className="mt-2"><Spark seed={fund.name.charCodeAt(0) * 7} up={fund.chg >= 0} /></div>

        <div className="mt-3 flex items-center gap-3 border-t border-line pt-3">
          <BandRing score={fund.score} size={44} stroke={5} />
          <div className="flex-1">
            <Pill label={vt} color={vc} />
            <div className="mt-1 text-[10.5px] text-ink-muted">Rank #{fund.rank} · {strength} band</div>
          </div>
          <span className="text-[11px] font-bold" style={{ color: riskColor(fund.risk) }}>{fund.risk}</span>
        </div>

        <div className="mt-3 grid grid-cols-4 gap-1.5">
          <MetricTile value={`${fund.r3}%`} label="3Y" tone="pos" />
          <MetricTile value={`${fund.r5}%`} label="5Y" tone="pos" />
          <MetricTile value={sipWord} label="SIP" />
          <MetricTile value={`${fund.exp}%`} label="Cost" />
        </div>

        <div className="mt-2.5 flex flex-wrap gap-1.5">
          <SoftPill><span className="h-[7px] w-[7px] rounded-full" style={{ background: DMMI_COLOR[fund.dmmi] ?? A }} />DMMI {fund.dmmi}</SoftPill>
          <SoftPill>{fmtAum(fund.aum)}</SoftPill>
        </div>
      </div>

      <div className="flex border-t border-line">
        {[
          { label: '👁 Details' },
          { label: '⇄ Compare', onClick: () => onToggle(index) },
          { label: '✕ Remove' },
          { label: 'View Fund', primary: true },
        ].map((b, i) => (
          <button key={i} type="button" onClick={b.onClick}
            className={cn(
              'flex flex-1 items-center justify-center gap-1.5 border-r border-line px-1 py-2.5 text-[11.5px] font-semibold last:border-r-0 transition-colors hover:bg-surface-2',
              b.primary ? 'font-bold text-royal' : 'text-ink-secondary hover:text-royal',
            )}>
            {b.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function FundsSection({ selected, onToggle }: { selected: Set<number>; onToggle: (i: number) => void }) {
  return (
    <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
      {FUNDS.map((f, i) => (
        <FundCard key={f.name} fund={f} index={i} selected={selected.has(i)} onToggle={onToggle} />
      ))}
    </div>
  );
}

// ── Rail wrapper (scrolls on phones, grids on larger screens) ────────────────
function Rail({ children, cols }: { children: React.ReactNode; cols: string }) {
  return (
    <div className={cn(
      'flex gap-3 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden',
      'sm:grid sm:overflow-visible', cols,
    )}>
      {children}
    </div>
  );
}

// ── S5 WHAT CHANGED ──────────────────────────────────────────────────────────
export function ChangedSection() {
  return (
    <Rail cols="sm:grid-cols-2 lg:grid-cols-3">
      {CHANGED.map(([fund, logo, lc, change, ic, col, time]) => (
        <div key={fund + time} className="flex w-[230px] shrink-0 items-start gap-3 rounded-xl border border-line bg-surface p-3.5 sm:w-auto">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-[9px] text-sm" style={{ background: `${col}1A`, color: col }} aria-hidden="true">{ic}</span>
          <div>
            <div className="text-xs font-bold text-ink"><MiniLogo letter={logo} color={lc} />{fund}</div>
            <div className="mt-0.5 text-[11.5px] leading-snug text-ink-secondary">{change}</div>
            <div className="mt-1.5 font-mono text-[10px] text-ink-faint">{time}</div>
          </div>
        </div>
      ))}
    </Rail>
  );
}

// ── S6 BEST OPPORTUNITIES ────────────────────────────────────────────────────
export function OpportunitiesSection() {
  return (
    <Rail cols="sm:grid-cols-2 lg:grid-cols-4">
      {OPPORTUNITIES.map(([cat, name, logo, col, val, sub]) => (
        <div key={cat} className="w-[160px] shrink-0 rounded-2xl border border-line bg-surface p-4 sm:w-auto">
          <div className="font-mono text-[9.5px] font-bold uppercase tracking-wide text-ink-muted">⭐ {cat}</div>
          <div className="mt-2.5 flex items-center gap-2.5">
            <Logo letter={logo} color={col} size={32} radius={9} font={12} />
            <div className="text-xs font-bold leading-tight text-ink">{name}</div>
          </div>
          <div className="mt-2.5 font-sans text-lg font-extrabold text-emerald">{val}</div>
          <div className="mt-0.5 text-[10.5px] text-ink-muted">{sub}</div>
        </div>
      ))}
    </Rail>
  );
}

// ── S7 DMMI ──────────────────────────────────────────────────────────────────
export function DmmiSection() {
  return (
    <Card className="p-5">
      <div className="grid items-center gap-6 lg:grid-cols-[230px_1fr]">
        <div className="text-center">
          <Semicircle val={DMMI.value} size={200} />
          <div className="mt-1.5 font-sans text-xl font-extrabold text-amber">{DMMI.mood}</div>
          <div className="mt-0.5 text-[11.5px] text-ink-muted">{DMMI.phase}</div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <DmmiColumn title="Best positioned now" color={E} rows={DMMI.best} valueColor={E} />
          <DmmiColumn title="At risk in this market" color={R} rows={DMMI.risk} valueColor={R} />
        </div>
      </div>
      <SoWhat><RichText text={DMMI.soWhat} /></SoWhat>
    </Card>
  );
}
function DmmiColumn({ title, color, rows, valueColor }: { title: string; color: string; rows: [string, string, string, string][]; valueColor: string }) {
  return (
    <div>
      <h5 className="mb-2 text-[11px] font-bold uppercase tracking-wide" style={{ color }}>{title}</h5>
      {rows.map(([n, l, c, d]) => (
        <div key={n} className="flex items-center gap-2.5 border-b border-line py-2 text-caption last:border-b-0">
          <Logo letter={l} color={c} size={24} radius={7} font={10} />
          <span className="flex-1 font-semibold text-ink">{n}</span>
          <span className="text-[11px] font-bold" style={{ color: valueColor }}>{d}</span>
        </div>
      ))}
    </div>
  );
}

// ── S8 PERFORMANCE ───────────────────────────────────────────────────────────
export function PerfSection() {
  const [tab, setTab] = React.useState(0);
  return (
    <Card className="p-5">
      <div className="mb-4 flex w-max max-w-full gap-1 overflow-x-auto rounded-xl bg-surface-2 p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {PERF_TABS.map((t, i) => (
          <button key={t} type="button" onClick={() => setTab(i)}
            className={cn('shrink-0 rounded-lg px-3.5 py-2 text-caption font-semibold transition-colors focus-visible:outline-none',
              i === tab ? 'bg-surface text-ink shadow-sm' : 'text-ink-muted hover:text-ink')}>
            {t}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-small">
          <thead>
            <tr>{PERF_HEAD.map((h, i) => (
              <th key={h} className={cn('border-b-2 border-line px-3 py-2.5 font-mono text-[10px] font-bold uppercase tracking-wide text-ink-muted', i === 0 ? 'text-left' : 'text-right')}>{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {PERF_ROWS.map((row, i) => {
              const dot = i === 0 ? B : i === 1 ? COLORS.S : O;
              return (
                <tr key={row[0] as string}>
                  <td className="border-b border-line px-3 py-3 text-left font-semibold text-ink last:border-b-0">
                    <span className="mr-1.5" style={{ color: dot }}>●</span>{row[0]}
                  </td>
                  {(row.slice(1) as number[]).map((v, j) => (
                    <td key={j} className={cn('border-b border-line px-3 py-3 text-right font-mono font-bold', i === 0 ? 'text-emerald' : 'text-ink-secondary')}>{v}%</td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ── S9 LEADERBOARD ───────────────────────────────────────────────────────────
export function LeaderboardSection() {
  const ranked = [...FUNDS].sort((a, b) => b.score - a.score);
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-small">
          <thead>
            <tr>
              {['#', 'Fund', 'Strength', 'Risk', '3Y Return', 'Momentum', 'Status'].map((h, i) => (
                <th key={h} className={cn('border-b-2 border-line px-3.5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-wide text-ink-muted', i <= 1 ? 'text-left' : 'text-right')}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ranked.map((f, i) => {
              const [mtxt, mcol] = momentumOf(f.status);
              const strength = STRENGTH_WORD[toStrength(f.score)];
              return (
                <tr key={f.name}>
                  <td className="border-b border-line px-3.5 py-3 text-left font-sans font-extrabold text-ink-muted last:border-b-0">{i + 1}</td>
                  <td className="border-b border-line px-3.5 py-3 text-left">
                    <div className="flex items-center gap-2.5">
                      <Logo letter={f.logo} color={f.color} size={30} radius={8} font={12} />
                      <div>
                        <div className="text-[12.5px] font-bold text-ink">{f.name}</div>
                        <div className="text-[10.5px] font-medium text-ink-muted">{f.cat}</div>
                      </div>
                    </div>
                  </td>
                  <td className="border-b border-line px-3.5 py-3 text-right">
                    <span className="inline-flex items-center justify-end gap-2">
                      <BandRing score={f.score} size={28} stroke={4} />
                      <span className="font-bold text-ink">{strength}</span>
                    </span>
                  </td>
                  <td className="border-b border-line px-3.5 py-3 text-right"><span className="text-[11px]" style={{ color: riskColor(f.risk) }}>{f.risk}</span></td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono font-bold text-emerald">+{f.r3}%</td>
                  <td className="border-b border-line px-3.5 py-3 text-right"><span className="text-[11px]" style={{ color: mcol }}>{mtxt}</span></td>
                  <td className="border-b border-line px-3.5 py-3 text-right"><span className="text-[10.5px] font-bold" style={{ color: mcol }}>{f.status}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ── S11 SMART ALERTS ─────────────────────────────────────────────────────────
export function AlertsSection() {
  return (
    <div className="grid grid-cols-1 gap-2.5 lg:grid-cols-2">
      {ALERTS.map(([title, desc, ic, col, time]) => (
        <div key={title + time} className="flex items-start gap-3 rounded-xl border border-line bg-surface p-3.5">
          <span className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-[10px] text-[15px]" style={{ background: `${col}1A`, color: col }} aria-hidden="true">{ic}</span>
          <div className="flex-1">
            <div className="text-[13px] font-bold text-ink">{title}</div>
            <div className="mt-0.5 text-[11.5px] leading-snug text-ink-muted">{desc}</div>
          </div>
          <span className="shrink-0 text-[10px] text-ink-faint">{time}</span>
        </div>
      ))}
    </div>
  );
}

// ── S12 SIMILAR FUNDS ────────────────────────────────────────────────────────
export function SimilarSection() {
  return (
    <Rail cols="sm:grid-cols-2 lg:grid-cols-3">
      {SIMILAR.map(([forTxt, name, logo, col, benefits]) => (
        <div key={name} className="w-[240px] shrink-0 rounded-2xl border border-line bg-surface p-4 sm:w-auto">
          <div className="text-[10.5px] font-semibold text-ink-muted">{forTxt}</div>
          <div className="my-2.5 flex items-center gap-2.5">
            <Logo letter={logo} color={col} size={34} radius={9} font={12} />
            <div className="text-[12.5px] font-bold text-ink">{name}</div>
          </div>
          <div className="flex flex-col gap-1.5">
            {benefits.map((b) => (
              <div key={b} className="flex items-center gap-2 text-[11px] text-ink-secondary">
                <span className="shrink-0 font-extrabold text-emerald">✓</span>{b}
              </div>
            ))}
          </div>
          <CTA variant="ghost" className="mt-3 w-full">+ Add to watchlist</CTA>
        </div>
      ))}
    </Rail>
  );
}

// ── S14 STATISTICS ───────────────────────────────────────────────────────────
export function StatsSection() {
  return (
    <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-[repeat(4,1fr)_1.2fr]">
      {STATS.map(([v, l, c]) => (
        <div key={l} className="rounded-2xl border border-line bg-surface p-4 text-center">
          <div className="font-sans text-[22px] font-extrabold" style={{ color: c }}>{v}</div>
          <div className="mt-1 text-[11px] font-semibold text-ink-muted">{l}</div>
        </div>
      ))}
      <div className="col-span-2 flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-4 lg:col-span-1">
        <Donut data={CATEGORY_MIX} size={90} thick={16} />
        <div>
          <div className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-ink-muted">Category Mix</div>
          {CATEGORY_MIX.slice(0, 4).map(([n, v, c]) => (
            <div key={n} className="flex items-center gap-1.5 py-px text-[11px] text-ink-secondary">
              <span className="h-2 w-2 rounded-sm" style={{ background: c }} />{n} · {v}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── S15 DISCOVERY ────────────────────────────────────────────────────────────
export function DiscoverySection() {
  return (
    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
      {DISCOVERY.map(([ic, t, d, col]) => (
        <button key={t} type="button"
          className="flex items-center gap-3 rounded-xl border border-line bg-surface p-3.5 text-left transition-all hover:-translate-y-0.5 hover:border-royal hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
          <span className="grid h-[38px] w-[38px] shrink-0 place-items-center rounded-[11px] text-[17px]" style={{ background: `${col}1A`, color: col }} aria-hidden="true">{ic}</span>
          <div>
            <div className="text-[12.5px] font-bold text-ink">{t}</div>
            <div className="mt-px text-[10.5px] text-ink-muted">{d}</div>
          </div>
        </button>
      ))}
    </div>
  );
}

// ── S16 RECENTLY VIEWED ──────────────────────────────────────────────────────
export function RecentlyViewedSection() {
  return (
    <div className="flex gap-3 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {RECENTLY_VIEWED.map(([name, logo, col, meta]) => (
        <div key={name} className="w-[200px] shrink-0 rounded-xl border border-line bg-surface p-3.5">
          <div className="flex items-center gap-2.5">
            <Logo letter={logo} color={col} size={32} radius={9} font={12} />
            <div className="min-w-0">
              <div className="text-xs font-bold leading-tight text-ink">{name}</div>
              <div className="text-[10px] text-ink-muted">{meta}</div>
            </div>
          </div>
          <CTA variant="ghost" className="mt-3 w-full">+ Add</CTA>
        </div>
      ))}
    </div>
  );
}

// ── S17 FAQ ──────────────────────────────────────────────────────────────────
export function FaqSection() {
  const [open, setOpen] = React.useState(0);
  return (
    <Card className="px-5 py-1">
      {FAQ.map(([q, a], i) => {
        const isOpen = open === i;
        return (
          <div key={q} className="border-b border-line last:border-b-0">
            <button type="button" onClick={() => setOpen(isOpen ? -1 : i)} aria-expanded={isOpen}
              className="flex w-full items-center justify-between gap-3 py-4 text-left text-[14px] font-semibold text-ink focus-visible:outline-none">
              {q}
              <svg className={cn('shrink-0 text-ink-muted transition-transform', isOpen && 'rotate-180')} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M6 9 L12 15 L18 9" />
              </svg>
            </button>
            {isOpen && <p className="m-0 max-w-[880px] pb-4 text-small leading-relaxed text-ink-muted">{a}</p>}
          </div>
        );
      })}
    </Card>
  );
}

// ── EMPTY STATE ──────────────────────────────────────────────────────────────
export function EmptyHero({ onViewSample }: { onViewSample: () => void }) {
  return (
    <div className="relative overflow-hidden rounded-3xl px-6 py-12 text-center text-white shadow-xl sm:px-10"
      style={{ background: 'linear-gradient(135deg,#0B1F3A,#15315C 55%,#1E40AF)' }}>
      <div className="pointer-events-none absolute -right-16 -top-20 h-80 w-80 rounded-full" style={{ background: 'radial-gradient(circle,rgba(37,99,235,.4),transparent 70%)' }} aria-hidden="true" />
      <div className="relative mx-auto max-w-[560px]">
        <div className="mx-auto mb-5 grid h-24 w-24 place-items-center rounded-3xl bg-white/10" aria-hidden="true">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3l2.5 6.5L21 10l-5 4.5L17.5 21 12 17l-5.5 4L8 14.5 3 10l6.5-.5z" />
          </svg>
        </div>
        <h1 className="font-sans text-[28px] font-extrabold leading-tight tracking-tight sm:text-[32px]">Start building your mutual fund watchlist</h1>
        <p className="mx-auto mt-3 max-w-md text-[15px] leading-relaxed text-slate-300">
          Save interesting funds and track their performance before investing. DhanRadar turns your watchlist into a daily decision center — not just a list of bookmarks.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href="/mf/explore" className="rounded-xl bg-white px-5 py-3 text-sm font-semibold text-navy transition-colors hover:bg-white/90">Explore Mutual Funds →</Link>
          <button type="button" onClick={onViewSample} className="rounded-xl border border-white/20 bg-white/10 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/20">View Sample Watchlist</button>
        </div>
      </div>
    </div>
  );
}

export function BenefitsGrid() {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {BENEFITS.map(([ic, t, d, col]) => (
        <div key={t} className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="mb-3 grid h-[38px] w-[38px] place-items-center rounded-[11px] text-lg" style={{ background: `${col}1A`, color: col }} aria-hidden="true">{ic}</div>
          <div className="text-[13.5px] font-bold text-ink">{t}</div>
          <div className="mt-1 text-[11.5px] leading-snug text-ink-muted">{d}</div>
        </div>
      ))}
    </div>
  );
}

// ── COMPARE TRAY (bottom, shows when funds selected) ─────────────────────────
export function CompareTray({ selected, onClear }: { selected: Set<number>; onClear: () => void }) {
  const show = selected.size > 0;
  return (
    <div className={cn(
      'fixed bottom-[78px] left-1/2 z-[54] flex max-w-[calc(100%-2rem)] -translate-x-1/2 items-center gap-3.5 rounded-2xl border border-line-strong bg-surface px-4 py-3 shadow-xl transition-transform duration-300',
      show ? 'translate-y-0' : 'pointer-events-none translate-y-[160px]',
    )}>
      <span className="text-caption font-bold text-ink">{selected.size} selected</span>
      <div className="flex">
        {[...selected].map((i) => (
          <span key={i} className="-ml-2 grid h-[30px] w-[30px] place-items-center rounded-lg border-2 border-surface font-sans text-[11px] font-extrabold text-white first:ml-0" style={{ background: FUNDS[i].color }} aria-hidden="true">
            {FUNDS[i].logo}
          </span>
        ))}
      </div>
      <span className="hidden text-[11px] text-ink-muted sm:inline">Select up to 4</span>
      <CTA variant="primary">Compare →</CTA>
      <CTA variant="ghost" onClick={onClear}>Clear</CTA>
    </div>
  );
}

// ── STICKY ACTION BAR ────────────────────────────────────────────────────────
export function StickyBar() {
  const actions = [
    { label: '+ Add Funds', primary: true },
    { label: '⇄ Compare' },
    { label: '⬇ Export' },
    { label: '🔍 Explore' },
  ];
  return (
    <div className="fixed bottom-4 left-1/2 z-[55] max-w-[calc(100%-1.25rem)] -translate-x-1/2 rounded-[16px] shadow-xl"
      style={{ background: 'rgba(11,31,58,.97)', backdropFilter: 'blur(12px)' }}>
      <div className="flex items-center gap-1.5 overflow-x-auto px-3 py-2.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {actions.map((a) => (
          <button key={a.label} type="button"
            className={cn('inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-xl border px-3.5 py-2 text-small font-semibold text-white transition-colors focus-visible:outline-none',
              a.primary ? 'border-royal bg-royal' : 'border-white/14 bg-white/10 hover:bg-white/20')}>
            {a.label}
          </button>
        ))}
      </div>
    </div>
  );
}

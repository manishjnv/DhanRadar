/**
 * Watchlist Monitor — section components (desktop + mobile, one responsive tree).
 *
 * Built 1:1 to the approved WatchlistPageV1 desktop + mobile mockups. Multi-col
 * grids collapse to a single column on phones; "rail" sections (What Changed,
 * Best Opportunities, Similar Funds, Recently Viewed) become horizontal
 * scrollers on phones and grids on larger screens — matching the mobile mockup.
 *
 * PREVIEW sections (unprefixed exports below) render illustrative sample data
 * from sampleData.ts — buttons are visual placeholders, no API, no business
 * logic. LIVE sections (the `Live*` exports, WATCHLIST_LIVE_DATA_PLAN.md
 * Wave 1) render the real `GET /mf/watchlist/cards` payload — band ring/word
 * only (no raw score, non-neg #2), no advisory verbs.
 */
'use client';

import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/cn';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import {
  Logo, BandRing, Donut, Card, RichText, CTA,
  Spark, RealSpark, Pill, Chip, MetricTile, MiniLogo, SoftPill,
} from './ui';
import {
  COLORS, FUNDS, type Fund, HERO, BENEFITS, AI_SUMMARY, INSIGHTS,
  FILTER_CHIPS, SORT_OPTIONS, OPPORTUNITIES, STATS, CATEGORY_MIX, DISCOVERY,
  FAQ, FILTER_GROUPS,
  toStrength, STRENGTH_WORD, riskColor, verdictOf, momentumOf, fmtAum, DMMI_COLOR,
} from './sampleData';
import { fundDisplayName } from '@/features/mf/fundDisplayName';
import { shortenAmcName } from '@/features/mf/explorer-format';
import { FundScoreCell } from '@/components/mf/explore/FundScoreCell';
import { CONFIDENCE_BAND_LABELS } from '@/lib/displayLabel';
import type { WatchlistCard, WatchlistChangeItem, WatchlistSimilarItem } from '@/features/mf/types';
import { useMoodCurrent } from '@/features/mood/api';
import { MoodGauge, REGIME_DISPLAY } from '@/components/mood/MoodGauge';
import { relativeTime } from '@/features/mood/relative-time';
import type { RecentlyViewedEntry } from '@/hooks/useRecentlyViewed';

const { B, A } = COLORS;

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

// ── LIVE S01/S11 AI SUMMARY + INSIGHTS (WATCHLIST_LIVE_DATA_PLAN.md Wave 3) ──
/** Renders the governed AI-gateway watchlist summary/insights (`GET
 *  /mf/watchlist/summary`). Empty `items` means a gate withheld output
 *  (consent/tier/gateway/confidence) — this NEVER falls back to sample text;
 *  it renders the honest "unavailable" state instead (non-neg #1/#9). */
export function LiveAiSection({
  items, disclosure, notAdvice,
}: {
  items: string[];
  disclosure?: string;
  notAdvice?: string;
}) {
  if (items.length === 0) {
    return <p className="text-caption text-ink-muted">AI summary unavailable right now</p>;
  }
  return (
    <div className="flex flex-col gap-3">
      <AiCardsGrid items={items} />
      <DisclosureBundle
        disclosure={disclosure}
        notAdvice={notAdvice || 'For education only — not investment advice.'}
      />
    </div>
  );
}

// ── S1 HERO ──────────────────────────────────────────────────────────────────
/** Real Hero KPI inputs (WATCHLIST_LIVE_DATA_PLAN.md Wave 1 item 4) — computed
 *  by the page from the `GET /mf/watchlist/cards` payload. */
export interface LiveHeroStats {
  fundsTracked: number;
  upToday: number;
  downToday: number;
  bandCounts: Record<'high' | 'medium' | 'low', number>;
  categoriesCovered: number;
}

export function HeroSection({ onCompare, stats }: { onCompare?: () => void; stats?: LiveHeroStats }) {
  const kpis = stats
    ? [
        { label: 'Funds Tracked', value: String(stats.fundsTracked) },
        { label: 'Up Today', value: String(stats.upToday), color: '#6EE7B7' },
        { label: 'Down Today', value: String(stats.downToday), color: '#FCA5A5' },
        { label: 'High Confidence', value: String(stats.bandCounts.high) },
        { label: 'Medium Confidence', value: String(stats.bandCounts.medium) },
        { label: 'Categories', value: String(stats.categoriesCovered) },
      ]
    : HERO.kpis;
  const sub = stats
    ? `${stats.fundsTracked} fund${stats.fundsTracked === 1 ? '' : 's'} you\u2019re tracking`
    : HERO.sub;

  return (
    <div className="relative overflow-hidden rounded-3xl px-6 py-6 text-white shadow-xl sm:px-7"
      style={{ background: 'linear-gradient(135deg,#0B1F3A 0%,#16335E 60%,#1E40AF 100%)' }}>
      <div className="pointer-events-none absolute -right-12 -top-16 h-72 w-72 rounded-full"
        style={{ background: 'radial-gradient(circle,rgba(37,99,235,.36),transparent 70%)' }} aria-hidden="true" />
      <div className="relative">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-sans text-[24px] font-extrabold tracking-tight">{HERO.title}</h1>
            <div className="mt-1 text-small text-slate-300">{sub}</div>
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
          {kpis.map((k) => (
            <div key={k.label} className="bg-white/[0.04] px-3.5 py-3">
              <div className="text-[9.5px] font-semibold uppercase leading-tight tracking-wide text-slate-400">{k.label}</div>
              <div className={cn('mt-1 font-sans font-extrabold leading-tight', 'small' in k && k.small ? 'text-sm' : 'text-[19px]')}
                style={{ color: k.color }}>
                {k.value}{'sub' in k && k.sub && <small className="ml-1 text-[11px] font-semibold opacity-85">{k.sub}</small>}
              </div>
            </div>
          ))}
        </div>

        {/* Summary pills — sample DMMI/label mix when illustrative; band-count
            breakdown (no mood/DMMI — that's Wave 2) when real. */}
        <div className="mt-4 flex flex-wrap gap-2.5">
          {stats
            ? (['high', 'medium', 'low'] as const)
                .filter((band) => stats.bandCounts[band] > 0)
                .map((band) => (
                  <span key={band} className="inline-flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/10 px-3 py-2 text-caption font-semibold">
                    <span className="font-mono font-extrabold">{stats.bandCounts[band]}</span> {CONFIDENCE_BAND_LABELS[band]}
                  </span>
                ))
            : HERO.summary.map((s, i) => (
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
      {DISCOVERY.map(([ic, t, d, col, href]) => (
        <Link key={t} href={href}
          className="flex items-center gap-3 rounded-xl border border-line bg-surface p-3.5 text-left transition-all hover:-translate-y-0.5 hover:border-royal hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
          <span className="grid h-[38px] w-[38px] shrink-0 place-items-center rounded-[11px] text-[17px]" style={{ background: `${col}1A`, color: col }} aria-hidden="true">{ic}</span>
          <div>
            <div className="text-[12.5px] font-bold text-ink">{t}</div>
            <div className="mt-px text-[10.5px] text-ink-muted">{d}</div>
          </div>
        </Link>
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
export interface CompareChip {
  key: string;
  letter: string;
  color: string;
}

export function CompareTray({
  selected, onClear, chips, compareHref,
}: {
  selected: Set<number>;
  onClear: () => void;
  /** Live override (WATCHLIST_LIVE_DATA_PLAN.md Wave 1) — render these avatar
   *  chips instead of indexing the illustrative FUNDS sample array. */
  chips?: CompareChip[];
  /** Live override — when set, "Compare →" navigates here (/mf/compare?isins=…)
   *  instead of being a decorative sample button. */
  compareHref?: string;
}) {
  const router = useRouter();
  const show = selected.size > 0;
  const items: CompareChip[] =
    chips ?? [...selected].map((i) => ({ key: String(i), letter: FUNDS[i]?.logo ?? '?', color: FUNDS[i]?.color ?? COLORS.S }));
  return (
    <div className={cn(
      'fixed bottom-[78px] left-1/2 z-[54] flex max-w-[calc(100%-2rem)] -translate-x-1/2 items-center gap-3.5 rounded-2xl border border-line-strong bg-surface px-4 py-3 shadow-xl transition-transform duration-300',
      show ? 'translate-y-0' : 'pointer-events-none translate-y-[160px]',
    )}>
      <span className="text-caption font-bold text-ink">{selected.size} selected</span>
      <div className="flex">
        {items.map((it) => (
          <span key={it.key} className="-ml-2 grid h-[30px] w-[30px] place-items-center rounded-lg border-2 border-surface font-sans text-[11px] font-extrabold text-white first:ml-0" style={{ background: it.color }} aria-hidden="true">
            {it.letter}
          </span>
        ))}
      </div>
      <span className="hidden text-[11px] text-ink-muted sm:inline">Select up to 4</span>
      <CTA variant="primary" onClick={compareHref ? () => router.push(compareHref) : undefined}>Compare →</CTA>
      <CTA variant="ghost" onClick={onClear}>Clear</CTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// LIVE sections (WATCHLIST_LIVE_DATA_PLAN.md Wave 1) — real `GET
// /mf/watchlist/cards` payload. Band ring/word only, no raw score (non-neg
// #2); no advisory verbs. Deterministic avatar colour keeps every live tile
// visually consistent with the PREVIEW palette without a stored brand map.
// ---------------------------------------------------------------------------

const AVATAR_PALETTE = [COLORS.N, COLORS.B, COLORS.E, COLORS.O, COLORS.V, COLORS.C, COLORS.A, COLORS.P, COLORS.T] as const;

function avatarColorFor(seedText: string): string {
  const code = (seedText.charCodeAt(0) || 0) + (seedText.charCodeAt(1) || 0);
  return AVATAR_PALETTE[code % AVATAR_PALETTE.length];
}

function liveFundName(card: WatchlistCard): string {
  return fundDisplayName(card.fund_name_short ?? card.scheme_name).name;
}

// ── LIVE S3 FUND CARD + GRID ─────────────────────────────────────────────────
function LiveFundCard({
  card, index, selected, onToggle, onRemove,
}: { card: WatchlistCard; index: number; selected: boolean; onToggle: (i: number) => void; onRemove: () => void }) {
  const name = liveFundName(card);
  const amc = card.amc_name ? shortenAmcName(card.amc_name) : null;
  const category = card.category ?? card.sebi_category;
  const color = avatarColorFor(card.isin);
  const letter = name[0]?.toUpperCase() ?? '?';

  return (
    <div className="relative flex flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-sm">
      <button type="button" onClick={() => onToggle(index)} aria-pressed={selected}
        aria-label={selected ? `Remove ${name} from comparison` : `Add ${name} to comparison`}
        className={cn(
          'absolute right-3 top-3 z-[3] grid h-[22px] w-[22px] place-items-center rounded-[7px] border-2 text-xs font-extrabold transition-colors',
          selected ? 'border-royal bg-royal text-white' : 'border-line-strong bg-surface text-transparent',
        )}>
        ✓
      </button>
      <div className="flex-1 p-4">
        <div className="flex items-start gap-3 pr-7">
          <Logo letter={letter} color={color} size={40} radius={11} font={15} />
          <div className="min-w-0">
            <div className="text-[13.5px] font-bold leading-tight text-ink">{name}</div>
            <div className="mt-0.5 text-[11px] text-ink-muted">{[amc, category].filter(Boolean).join(' · ')}</div>
          </div>
        </div>

        <div className="mt-3 flex items-end justify-between">
          <div>
            <div className="font-mono text-lg font-extrabold text-ink">
              {card.nav_latest != null ? `₹${card.nav_latest.toFixed(2)}` : '—'}
            </div>
            <div className="text-[9.5px] font-semibold uppercase tracking-wide text-ink-muted">NAV</div>
          </div>
          {card.nav_change_pct != null && (
            <div className="text-right">
              <div className={cn('font-mono text-xs font-bold', card.nav_change_pct >= 0 ? 'text-emerald' : 'text-red')}>
                {card.nav_change_pct >= 0 ? '+' : ''}{card.nav_change_pct.toFixed(2)}%
              </div>
              <div className="text-[9.5px] text-ink-muted">today</div>
            </div>
          )}
        </div>

        {card.nav_sparkline.length > 1 && (
          <div className="mt-2">
            <RealSpark points={card.nav_sparkline} up={(card.nav_change_pct ?? 0) >= 0} />
          </div>
        )}

        <div className="mt-3 flex items-center gap-3 border-t border-line pt-3">
          <FundScoreCell label={card.verb_label ?? 'insufficient_data'} confidenceBand={card.confidence_band} ringSize={44} />
        </div>

        <div className="mt-3 grid grid-cols-3 gap-1.5">
          <MetricTile value={card.return_1y_pct != null ? `${card.return_1y_pct.toFixed(1)}%` : '—'} label="1Y" tone="pos" />
          <MetricTile value={card.return_3y_pct != null ? `${card.return_3y_pct.toFixed(1)}%` : '—'} label="3Y" tone="pos" />
          <MetricTile value={card.expense_ratio_pct != null ? `${card.expense_ratio_pct.toFixed(2)}%` : '—'} label="Cost" />
        </div>

        {card.risk_o_meter && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            <SoftPill>{card.risk_o_meter}</SoftPill>
          </div>
        )}
      </div>

      <div className="flex border-t border-line">
        <Link href={`/mf/fund/${card.isin}`}
          className="flex flex-1 items-center justify-center gap-1.5 border-r border-line px-1 py-2.5 text-[11.5px] font-semibold text-ink-secondary transition-colors hover:bg-surface-2 hover:text-royal">
          👁 Details
        </Link>
        <button type="button" onClick={() => onToggle(index)}
          className="flex flex-1 items-center justify-center gap-1.5 border-r border-line px-1 py-2.5 text-[11.5px] font-semibold text-ink-secondary transition-colors hover:bg-surface-2 hover:text-royal">
          ⇄ Compare
        </button>
        <button type="button" onClick={onRemove}
          className="flex flex-1 items-center justify-center gap-1.5 border-r border-line px-1 py-2.5 text-[11.5px] font-semibold text-ink-secondary transition-colors hover:bg-surface-2 hover:text-royal">
          ✕ Remove
        </button>
        <Link href={`/mf/fund/${card.isin}`}
          className="flex flex-1 items-center justify-center gap-1.5 px-1 py-2.5 text-[11.5px] font-bold text-royal transition-colors hover:bg-surface-2">
          View Fund
        </Link>
      </div>
    </div>
  );
}

export function LiveFundsSection({
  cards, selected, onToggle, onRemove,
}: { cards: WatchlistCard[]; selected: Set<number>; onToggle: (i: number) => void; onRemove: (isin: string) => void }) {
  if (cards.length === 0) {
    return <p className="text-caption text-ink-muted">No funds match the current search/filter.</p>;
  }
  return (
    <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map((c, i) => (
        <LiveFundCard key={c.isin} card={c} index={i} selected={selected.has(i)} onToggle={onToggle} onRemove={() => onRemove(c.isin)} />
      ))}
    </div>
  );
}

// ── LIVE S2 FILTER & SORT ────────────────────────────────────────────────────
export type LiveSortKey = 'recent' | 'return_1y_desc' | 'return_3y_desc' | 'name_asc';

/** Same `sort` state drives both the <select> value and this comparator — the
 *  selected option can never drift from the sort actually applied (the
 *  "atomic with headers" leaderboard trap the plan calls out). */
export function sortWatchlistCards(cards: WatchlistCard[], sort: LiveSortKey): WatchlistCard[] {
  const out = [...cards];
  switch (sort) {
    case 'return_1y_desc':
      out.sort((a, b) => (b.return_1y_pct ?? -Infinity) - (a.return_1y_pct ?? -Infinity));
      break;
    case 'return_3y_desc':
      out.sort((a, b) => (b.return_3y_pct ?? -Infinity) - (a.return_3y_pct ?? -Infinity));
      break;
    case 'name_asc':
      out.sort((a, b) => liveFundName(a).localeCompare(liveFundName(b)));
      break;
    case 'recent':
    default:
      break; // keep the payload's own (watchlist-add) order
  }
  return out;
}

export function watchlistCardMatchesSearch(card: WatchlistCard, search: string): boolean {
  const q = search.trim().toLowerCase();
  if (!q) return true;
  const haystack = [card.fund_name_short, card.scheme_name, card.amc_name].filter(Boolean).join(' ').toLowerCase();
  return haystack.includes(q);
}

export function LiveFilterSection({
  search, onSearchChange, sort, onSortChange,
}: { search: string; onSearchChange: (v: string) => void; sort: LiveSortKey; onSortChange: (v: LiveSortKey) => void }) {
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="relative min-w-[200px] flex-1 sm:max-w-[320px]">
          <svg className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <circle cx="11" cy="11" r="7" /><path d="M16 16 L21 21" />
          </svg>
          <input type="search" value={search} onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search watchlist…" aria-label="Search watchlist"
            className="h-10 w-full rounded-xl border border-line-strong bg-surface pl-9 pr-3 text-small text-ink outline-none focus:border-royal focus:ring-2 focus:ring-royal/20" />
        </div>
        <label className="ml-auto flex items-center gap-2 text-caption text-ink-muted">
          Sort
          <select value={sort} onChange={(e) => onSortChange(e.target.value as LiveSortKey)}
            className="cursor-pointer rounded-lg border border-line-strong bg-surface px-2.5 py-2 text-caption font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
            <option value="recent">Recently Added</option>
            <option value="return_1y_desc">1Y Return</option>
            <option value="return_3y_desc">3Y Return</option>
            <option value="name_asc">Alphabetical</option>
          </select>
        </label>
      </div>
    </Card>
  );
}

// ── LIVE S5 CATEGORY LEADERS (renamed from "Best Opportunities") ────────────
export interface CategoryLeader {
  category: string;
  card: WatchlistCard;
}

export function computeCategoryLeaders(cards: WatchlistCard[]): CategoryLeader[] {
  const byCategory = new Map<string, WatchlistCard>();
  for (const c of cards) {
    const category = c.category ?? c.sebi_category;
    if (!category || c.return_1y_pct == null) continue;
    const cur = byCategory.get(category);
    if (!cur || (cur.return_1y_pct ?? -Infinity) < c.return_1y_pct) byCategory.set(category, c);
  }
  return [...byCategory.entries()].map(([category, card]) => ({ category, card }));
}

export function LiveCategoryLeadersSection({ leaders }: { leaders: CategoryLeader[] }) {
  if (leaders.length === 0) {
    return <p className="text-caption text-ink-muted">Add funds across different categories to see category leaders here.</p>;
  }
  return (
    <Rail cols="sm:grid-cols-2 lg:grid-cols-4">
      {leaders.map(({ category, card }) => {
        const name = liveFundName(card);
        const color = avatarColorFor(card.isin);
        return (
          <div key={category} className="w-[160px] shrink-0 rounded-2xl border border-line bg-surface p-4 sm:w-auto">
            <div className="font-mono text-[9.5px] font-bold uppercase tracking-wide text-ink-muted">⭐ {category}</div>
            <div className="mt-2.5 flex items-center gap-2.5">
              <Logo letter={name[0]?.toUpperCase() ?? '?'} color={color} size={32} radius={9} font={12} />
              <div className="text-xs font-bold leading-tight text-ink">{name}</div>
            </div>
            <div className="mt-2.5 font-sans text-lg font-extrabold text-emerald">
              {card.return_1y_pct != null ? `${card.return_1y_pct.toFixed(1)}%` : '—'}
            </div>
            <div className="mt-0.5 text-[10.5px] text-ink-muted">1Y return, in your watchlist</div>
          </div>
        );
      })}
    </Rail>
  );
}

// ── LIVE S8 LEADERBOARD ──────────────────────────────────────────────────────
export function LiveLeaderboardSection({ cards }: { cards: WatchlistCard[] }) {
  const ranked = React.useMemo(
    () => [...cards].sort((a, b) => (b.return_1y_pct ?? -Infinity) - (a.return_1y_pct ?? -Infinity)),
    [cards],
  );
  if (ranked.length === 0) {
    return <p className="text-caption text-ink-muted">Save funds to see them ranked here.</p>;
  }
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-small">
          <thead>
            <tr>
              {['#', 'Fund', 'Label', 'Risk', '1Y Return'].map((h, i) => (
                <th key={h} className={cn('border-b-2 border-line px-3.5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-wide text-ink-muted', i <= 1 ? 'text-left' : 'text-right')}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ranked.map((c, i) => {
              const name = liveFundName(c);
              const color = avatarColorFor(c.isin);
              return (
                <tr key={c.isin}>
                  <td className="border-b border-line px-3.5 py-3 text-left font-sans font-extrabold text-ink-muted last:border-b-0">{i + 1}</td>
                  <td className="border-b border-line px-3.5 py-3 text-left">
                    <div className="flex items-center gap-2.5">
                      <Logo letter={name[0]?.toUpperCase() ?? '?'} color={color} size={30} radius={8} font={12} />
                      <div>
                        <div className="text-[12.5px] font-bold text-ink">{name}</div>
                        <div className="text-[10.5px] font-medium text-ink-muted">{c.category ?? c.sebi_category ?? '—'}</div>
                      </div>
                    </div>
                  </td>
                  <td className="border-b border-line px-3.5 py-3 text-right">
                    <FundScoreCell label={c.verb_label ?? 'insufficient_data'} confidenceBand={c.confidence_band} ringSize={28} />
                  </td>
                  <td className="border-b border-line px-3.5 py-3 text-right"><span className="text-[11px] text-ink-secondary">{c.risk_o_meter ?? '—'}</span></td>
                  <td className={cn('border-b border-line px-3.5 py-3 text-right font-mono font-bold', (c.return_1y_pct ?? 0) >= 0 ? 'text-emerald' : 'text-red')}>
                    {c.return_1y_pct != null ? `${c.return_1y_pct >= 0 ? '+' : ''}${c.return_1y_pct.toFixed(1)}%` : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ── LIVE S11 STATISTICS ──────────────────────────────────────────────────────
export function LiveStatsSection({ cards }: { cards: WatchlistCard[] }) {
  const withReturn = cards.filter((c) => c.return_1y_pct != null);
  const avgReturn = withReturn.length
    ? withReturn.reduce((s, c) => s + (c.return_1y_pct ?? 0), 0) / withReturn.length
    : null;
  const withExpense = cards.filter((c) => c.expense_ratio_pct != null);
  const avgExpense = withExpense.length
    ? withExpense.reduce((s, c) => s + (c.expense_ratio_pct ?? 0), 0) / withExpense.length
    : null;

  const bandCounts: Record<'high' | 'medium' | 'low', number> = { high: 0, medium: 0, low: 0 };
  for (const c of cards) if (c.confidence_band) bandCounts[c.confidence_band] += 1;
  const topBand = (Object.entries(bandCounts) as ['high' | 'medium' | 'low', number][])
    .sort((a, b) => b[1] - a[1])[0];

  const catCounts = new Map<string, number>();
  for (const c of cards) {
    const category = c.category ?? c.sebi_category ?? 'Other';
    catCounts.set(category, (catCounts.get(category) ?? 0) + 1);
  }
  const categoryMix: [string, number, string][] = [...catCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([name, count], i) => [name, count, AVATAR_PALETTE[i % AVATAR_PALETTE.length]]);

  const stats: [string, string, string][] = [
    [avgReturn != null ? `${avgReturn >= 0 ? '+' : ''}${avgReturn.toFixed(1)}%` : '—', 'Avg 1Y Return', COLORS.E],
    [topBand && topBand[1] > 0 ? CONFIDENCE_BAND_LABELS[topBand[0]] : '—', 'Most Common Confidence', COLORS.B],
    [avgExpense != null ? `${avgExpense.toFixed(2)}%` : '—', 'Avg Cost', 'var(--ink, #0F172A)'],
    [String(cards.length), 'Funds Tracked', COLORS.B],
  ];

  return (
    <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-[repeat(4,1fr)_1.2fr]">
      {stats.map(([v, l, c]) => (
        <div key={l} className="rounded-2xl border border-line bg-surface p-4 text-center">
          <div className="font-sans text-[22px] font-extrabold" style={{ color: c }}>{v}</div>
          <div className="mt-1 text-[11px] font-semibold text-ink-muted">{l}</div>
        </div>
      ))}
      <div className="col-span-2 flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-4 lg:col-span-1">
        <Donut data={categoryMix} size={90} thick={16} />
        <div>
          <div className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-ink-muted">Category Mix</div>
          {categoryMix.slice(0, 4).map(([n, v, c]) => (
            <div key={n} className="flex items-center gap-1.5 py-px text-[11px] text-ink-secondary">
              <span className="h-2 w-2 rounded-sm" style={{ background: c }} />{n} · {v}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// LIVE sections (WATCHLIST_LIVE_DATA_PLAN.md Wave 2) — What Changed, Similar
// Funds, DMMI, Performance, Recently Viewed. Same #2/#1 discipline as Wave 1's
// Live* sections above: band/word only, no advisory verb, no raw score.
// ---------------------------------------------------------------------------

const CHANGE_SEVERITY_ICON: Record<WatchlistChangeItem['severity'], string> = { notable: '⚠', info: 'ℹ' };
const CHANGE_SEVERITY_COLOR: Record<WatchlistChangeItem['severity'], string> = { notable: COLORS.A, info: COLORS.B };

// ── LIVE S04 WHAT CHANGED ─────────────────────────────────────────────────────
export function LiveChangedSection({ items }: { items: WatchlistChangeItem[] }) {
  if (items.length === 0) {
    return <p className="text-caption text-ink-muted">No tracked changes yet — check back after the next update.</p>;
  }
  return (
    <Rail cols="sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => {
        const name = fundDisplayName(item.fund_name_short ?? item.scheme_name).name;
        const color = avatarColorFor(item.isin);
        const icon = CHANGE_SEVERITY_ICON[item.severity];
        const sevColor = CHANGE_SEVERITY_COLOR[item.severity];
        return (
          <div key={`${item.isin}-${item.event_type}-${item.as_of}`} className="flex w-[230px] shrink-0 items-start gap-3 rounded-xl border border-line bg-surface p-3.5 sm:w-auto">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-[9px] text-sm" style={{ background: `${sevColor}1A`, color: sevColor }} aria-hidden="true">
              {icon}
            </span>
            <div>
              <div className="text-xs font-bold text-ink"><MiniLogo letter={name[0]?.toUpperCase() ?? '?'} color={color} />{name}</div>
              <div className="mt-0.5 text-[11.5px] leading-snug text-ink-secondary">{item.summary}</div>
              <div className="mt-1.5 font-mono text-[10px] text-ink-faint">{relativeTime(item.as_of)}</div>
            </div>
          </div>
        );
      })}
    </Rail>
  );
}

// ── LIVE S06 DMMI ─────────────────────────────────────────────────────────────
export function LiveDmmiSection() {
  const { data, isLoading } = useMoodCurrent();
  const healthy =
    !!data && data.data_quality !== 'unavailable' &&
    data.regime !== 'data_unavailable' && data.regime !== 'insufficient_data';

  if (isLoading) {
    return <Card className="p-5"><p className="text-caption text-ink-muted">Loading market mood…</p></Card>;
  }
  if (!data || !healthy) {
    return <Card className="p-5"><p className="text-caption text-ink-muted">Market mood is temporarily unavailable.</p></Card>;
  }

  const word = REGIME_DISPLAY[data.regime] ?? REGIME_DISPLAY.insufficient_data;
  return (
    <Card className="p-5">
      <div className="grid items-center gap-6 lg:grid-cols-[230px_1fr]">
        <div className="flex justify-center">
          <MoodGauge regime={data.regime} confidenceBand={data.confidence_band} />
        </div>
        <div>
          <p className="text-small leading-relaxed text-ink-secondary">
            Market mood reads <span className="font-semibold text-ink">{word}</span> today. DMMI describes
            present market conditions — it does not predict what happens next, and it is not
            personalised to any specific fund in your watchlist.
          </p>
          <Link href="/mood" className="mt-3 inline-flex items-center gap-1 text-caption font-semibold text-royal hover:underline">
            See the full Market Mood breakdown →
          </Link>
        </div>
      </div>
    </Card>
  );
}

// ── LIVE S07 PERFORMANCE ──────────────────────────────────────────────────────
function meanOfReturns(values: (number | null | undefined)[]): number | null {
  const nums = values.filter((v): v is number => v != null);
  return nums.length ? nums.reduce((s, v) => s + v, 0) / nums.length : null;
}

export function LivePerfSection({ cards }: { cards: WatchlistCard[] }) {
  const rows: { label: string; r1: number | null; r3: number | null; r5: number | null }[] = [
    {
      label: 'Your watchlist (avg)',
      r1: meanOfReturns(cards.map((c) => c.return_1y_pct)),
      r3: meanOfReturns(cards.map((c) => c.return_3y_pct)),
      r5: meanOfReturns(cards.map((c) => c.return_5y_pct)),
    },
    {
      // No mf_category_stats metric_key covers a 5Y window — never fabricated.
      label: 'Category average',
      r1: meanOfReturns(cards.map((c) => c.category_return_1y_pct)),
      r3: meanOfReturns(cards.map((c) => c.category_return_3y_pct)),
      r5: null,
    },
  ];
  const fmt = (v: number | null) => (v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : '—');

  return (
    <Card className="p-5">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-small">
          <thead>
            <tr>{['Series', '1Y', '3Y', '5Y'].map((h, i) => (
              <th key={h} className={cn('border-b-2 border-line px-3 py-2.5 font-mono text-[10px] font-bold uppercase tracking-wide text-ink-muted', i === 0 ? 'text-left' : 'text-right')}>{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row.label}>
                <td className="border-b border-line px-3 py-3 text-left font-semibold text-ink last:border-b-0">
                  <span className="mr-1.5" style={{ color: i === 0 ? B : COLORS.S }}>●</span>{row.label}
                </td>
                {[row.r1, row.r3, row.r5].map((v, j) => (
                  <td key={j} className={cn('border-b border-line px-3 py-3 text-right font-mono font-bold', v != null && v >= 0 ? 'text-emerald' : 'text-ink-secondary')}>{fmt(v)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-caption text-ink-faint">Benchmark comparison coming.</p>
    </Card>
  );
}

// ── LIVE S10 SIMILAR FUNDS ────────────────────────────────────────────────────
export function LiveSimilarSection({
  items, onAdd,
}: { items: WatchlistSimilarItem[]; onAdd: (isin: string, name: string) => void }) {
  if (items.length === 0) {
    return <p className="text-caption text-ink-muted">Add more funds to your watchlist to see similar funds here.</p>;
  }
  return (
    <Rail cols="sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => {
        const name = fundDisplayName(item.fund_name_short ?? item.scheme_name).name;
        const color = avatarColorFor(item.isin);
        return (
          <div key={item.isin} className="w-[240px] shrink-0 rounded-2xl border border-line bg-surface p-4 sm:w-auto">
            <div className="text-[10.5px] font-semibold text-ink-muted">
              {item.similar_to ? `Funds similar to ${item.similar_to}` : 'Similar to funds in your watchlist'}
            </div>
            <div className="my-2.5 flex items-center gap-2.5">
              <Logo letter={name[0]?.toUpperCase() ?? '?'} color={color} size={34} radius={9} font={12} />
              <div className="text-[12.5px] font-bold text-ink">{name}</div>
            </div>
            <FundScoreCell label={item.verb_label ?? 'insufficient_data'} confidenceBand={item.confidence_band} ringSize={32} />
            <div className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-secondary">
              {item.return_1y_pct != null && <span>1Y {item.return_1y_pct.toFixed(1)}%</span>}
              {item.return_3y_pct != null && <span>3Y {item.return_3y_pct.toFixed(1)}%</span>}
              {item.expense_ratio_pct != null && <span>Cost {item.expense_ratio_pct.toFixed(2)}%</span>}
            </div>
            <CTA variant="ghost" className="mt-3 w-full" onClick={() => onAdd(item.isin, name)}>+ Add</CTA>
          </div>
        );
      })}
    </Rail>
  );
}

// ── LIVE S13 RECENTLY VIEWED ──────────────────────────────────────────────────
export function LiveRecentlyViewedSection({
  entries, onAdd,
}: { entries: RecentlyViewedEntry[]; onAdd: (isin: string, name: string) => void }) {
  if (entries.length === 0) {
    return <p className="text-caption text-ink-muted">Funds you view will show up here.</p>;
  }
  return (
    <div className="flex gap-3 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {entries.map((e) => {
        const color = avatarColorFor(e.isin);
        return (
          <div key={e.isin} className="w-[200px] shrink-0 rounded-xl border border-line bg-surface p-3.5">
            <div className="flex items-center gap-2.5">
              <Logo letter={e.name[0]?.toUpperCase() ?? '?'} color={color} size={32} radius={9} font={12} />
              <div className="min-w-0">
                <Link href={`/mf/fund/${e.isin}`} className="block truncate text-xs font-bold leading-tight text-ink hover:text-royal">{e.name}</Link>
                <div className="text-[10px] text-ink-muted">{relativeTime(e.at)}</div>
              </div>
            </div>
            <CTA variant="ghost" className="mt-3 w-full" onClick={() => onAdd(e.isin, e.name)}>+ Add</CTA>
          </div>
        );
      })}
    </div>
  );
}


/**
 * Rankings & Leaderboards V1 — section components.
 *
 * Each export is one numbered section of the approved LeaderboardPageV1 mockup,
 * built responsive: the Top 100 + Manager + AMC tables render as full tables on
 * large screens and as the dedicated mobile card/list layouts below `lg`; rails
 * scroll horizontally at every size; grids collapse to one column on phones.
 *
 * Most sections still render illustrative preview data (sampleData.ts). Sections
 * that accept a `live`/`boards` prop (Top100, Champions, Performance, Sip, Risk,
 * Value, Flows, Improved, AMC, Trending) swap in real GET /mf/leaderboard rows
 * when the caller (page.tsx) passes them — falling back to the untouched sample
 * whenever a board key is absent. No numeric DhanRadar score ever renders; live
 * rows carry only the verb_label/confidence_band enum (non-neg #2).
 */
'use client';

import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/cn';
import {
  Logo, BandRing, BandRingLive, Semicircle, MiniSpark, EduPill, RiskBadge, Card, SoWhat,
  RichText, HScroll, IconBtn, CTA, DiscCard, MiniLbCard, PortfolioIsinsContext, PortfolioPill,
} from './ui';
import {
  COLORS, FUNDS, DISC, CHAMP, DMMI, MGR, AMC, AI_INSIGHTS, FAQ, CATNAV,
  HERO_KPIS, HERO_QUICK, REGIME_EXPLAINER,
  PERF_RAIL, SIP_RAIL, RISK_RAIL, VALUE_RAIL, INTEL_RAIL, FLOW_RAIL, IMPROVED_RAIL, TREND_RAIL,
  eduLabel, eduWordFromLabel, toStrength, STRENGTH_WORD, STRENGTH_COLOR, aum,
  type Fund, type Rail, type RailRow,
} from './sampleData';
import { EmptyState } from '@/components/ui/EmptyState';
import { LiveBadge } from '@/components/mf/funddetail/parts';
import type {
  LeaderboardHero, LeaderboardBoards, LbBoard,
  LbFundRow, LbChampionRow, LbLabelUpgradeRow, LbAmcFactRow, LbManagerRow, LbInsightRow,
} from '@/features/mf/types';

const { E } = COLORS;

// ═══════════════════════════════════════════════════════════════════════════
// Live-data helpers shared across sections — reused everywhere a real board
// row needs to become a decorative tile/table row. No numeric score anywhere;
// bands/labels come straight off the enum (eduWordFromLabel), never derived
// from a hidden number (non-neg #2).
// ═══════════════════════════════════════════════════════════════════════════
const LOGO_PALETTE = Object.values(COLORS);
/** Deterministic decorative colour for a live entity (fund/AMC/category) — no
 * brand colour exists for real rows, so this just keeps tiles visually varied. */
function colorFor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h + key.charCodeAt(i)) % 997;
  return LOGO_PALETTE[h % LOGO_PALETTE.length];
}
function initialOf(name: string): string {
  return (name.charAt(0) || 'F').toUpperCase();
}
function fundName(r: LbFundRow): string {
  return r.fund_name_short ?? r.scheme_name;
}
/** Returns with 1 decimal + '%', signed (matches Top100/rail sample convention). */
function pctSigned(v: number | null | undefined): string {
  if (v == null) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
}
/** Returns with 1 decimal + '%', unsigned (matches Champions sample convention). */
function pct1(v: number | null | undefined): string {
  return v == null ? '—' : `${v.toFixed(1)}%`;
}
function ter1(v: number | null | undefined): string {
  return v == null ? '—' : `${v.toFixed(2)}%`;
}
/** Rank deltas '+N' / '−N' (U+2212 minus, per spec). */
function fmtDelta(n: number | null | undefined): string {
  if (n == null) return '—';
  if (n === 0) return '0';
  return n > 0 ? `+${n}` : `−${Math.abs(n)}`;
}
/** Board-specific headline value — the wire unit key maps to a display suffix
 * ('pct_mom_aum' → '+52.3%', 'return_per_ter' → '36×'); unknown units render
 * the bare number rather than leaking the unit key into the UI. */
const METRIC_SUFFIX: Record<string, string> = {
  pct_mom_aum: '%', return_per_ter: '×', x_since_launch: '×', pct_sip_xirr: '%',
};
function metricVal(r: LbFundRow): string {
  if (r.metric_value == null) return '—';
  const suffix = METRIC_SUFFIX[r.metric_unit ?? ''] ?? '';
  const sign = suffix === '%' && r.metric_value >= 0 ? '+' : '';
  return `${sign}${r.metric_value.toFixed(suffix === '×' ? 0 : 1)}${suffix}`;
}
/** SIP rails render the bare XIRR number ('28.1', matching the sample's
 * unsuffixed style) — never metricVal's %/sign formatting. */
function sipXirrVal(r: LbFundRow): string {
  return r.metric_value == null ? '—' : r.metric_value.toFixed(1);
}
/** sip_consistency's metric_value is 0-100 ("% of rolling 1Y windows
 * positive") — banded into a word, the raw pct never reaches the DOM. */
function sipConsistencyWord(r: LbFundRow): string {
  const v = r.metric_value;
  if (v == null) return '—';
  return v >= 85 ? 'Strong' : v >= 70 ? 'Good' : 'Fair';
}
/** risk_recovery's metric_value is days; the rail displays rounded months. */
function recoveryMonths(r: LbFundRow): string {
  return r.metric_value == null ? '—' : `${Math.round(r.metric_value / 30)} mo`;
}
/** V1 — `catAvg` is the SEBI-category average of the SAME metric `val` renders
 *  (only pass it from return/sip/TER rails, whose metric is a plain percentage —
 *  a rank/word/multiple rail has no comparable "cat avg %" to show). Absent or
 *  null → row renders exactly as before (no sub line). */
function fundRailRow(r: LbFundRow, val: string, up?: boolean, catAvg?: number | null): RailRow {
  const name = fundName(r);
  const sub = catAvg != null ? `cat avg ${catAvg.toFixed(1)}%` : undefined;
  return { name, logo: initialOf(name), color: colorFor(r.isin), val, up, href: `/mf/fund/${r.isin}`, sub, isin: r.isin };
}
function upgradeRailRow(r: LbLabelUpgradeRow): RailRow {
  const name = fundName(r);
  const from = eduWordFromLabel(r.label_from).word;
  const to = eduWordFromLabel(r.label_to).word;
  return { name, logo: initialOf(name), color: colorFor(r.isin), val: `${from} → ${to}`, up: true, href: `/mf/fund/${r.isin}`, isin: r.isin };
}
/** Marks a rail live and swaps in real rows — used for MIXED-coverage sections
 * (per-rail chip, not a section badge). Absent board → untouched sample rail. */
function liveRail<T>(sample: Rail, board: { rows: T[] } | undefined, mapRow: (row: T) => RailRow): Rail {
  if (!board) return sample;
  return { ...sample, rows: board.rows.map(mapRow), live: true };
}
/** Same swap without the `live` flag — used inside FULLY-covered sections that
 * already carry one section-level LiveBadge (no need to repeat it per rail). */
function wiredRail<T>(sample: Rail, board: { rows: T[] } | undefined, mapRow: (row: T) => RailRow): Rail {
  return board ? { ...sample, rows: board.rows.map(mapRow) } : sample;
}
/** Picks wiredRail (all 4 boards present, section carries one header badge)
 * vs liveRail (mixed coverage, per-rail chip) — shared by PerformanceSection
 * and RiskSection, whose 4th rail can go either way. */
function coverageRail<T>(allLive: boolean, sample: Rail, board: { rows: T[] } | undefined, mapRow: (row: T) => RailRow): Rail {
  return allLive ? wiredRail(sample, board, mapRow) : liveRail(sample, board, mapRow);
}

// Ring cell — score band (sample) vs label/confidence band (live), same visual shape.
type RingSpec = { kind: 'score'; score: number } | { kind: 'band'; band: 'high' | 'medium' | 'low'; color: string };
function RingCell({ ring, size, stroke }: { ring: RingSpec; size?: number; stroke?: number }) {
  return ring.kind === 'score'
    ? <BandRing score={ring.score} size={size} stroke={stroke} />
    : <BandRingLive band={ring.band} color={ring.color} size={size} stroke={stroke} />;
}

// Section anchor wrapper — id + scroll-margin so the sticky nav lands cleanly.
export function Anchor({ id, children, className }: { id?: string; children: React.ReactNode; className?: string }) {
  return <section id={id} className={cn('mt-8 scroll-mt-28', className)}>{children}</section>;
}

// ═══════════════════════════════════════════════════════════════════════════
// S1 — HERO
// ═══════════════════════════════════════════════════════════════════════════
export function HeroSection({ hero, moodWord, moodBand, moodColor }: {
  hero?: LeaderboardHero;
  moodWord?: string;
  moodBand?: string;
  moodColor?: string;
} = {}) {
  const [active, setActive] = React.useState(0);
  const kpis: (typeof HERO_KPIS[number] & { href?: string })[] = hero ? [
    { label: 'Funds Ranked', value: hero.funds_ranked.toLocaleString('en-IN') },
    { label: 'Categories', value: String(hero.categories) },
    { label: 'Live Boards', value: String(hero.live_board_count) },
    {
      label: 'Top Rated Today',
      value: hero.top_fund ? (hero.top_fund.fund_name_short ?? hero.top_fund.scheme_name) : '—',
      small: true,
      href: hero.top_fund ? `/mf/fund/${hero.top_fund.isin}` : undefined,
    },
    { label: 'Trending', value: hero.trending_category ?? '—', small: true },
    {
      label: 'DMMI',
      value: moodWord ?? HERO_KPIS[5].value,
      sub: moodWord ? (moodBand ? `${moodBand[0].toUpperCase()}${moodBand.slice(1)}` : undefined) : HERO_KPIS[5].sub,
      valueColor: moodColor ?? HERO_KPIS[5].valueColor,
      small: !!moodWord,
    },
  ] : HERO_KPIS;
  return (
    <div className="relative overflow-hidden rounded-[24px] p-7 text-white shadow-lg sm:p-8" style={{ background: 'linear-gradient(135deg,#0B1F3A 0%,#16335E 58%,#1E40AF 100%)' }}>
      <div className="pointer-events-none absolute -right-12 -top-16 h-80 w-80 rounded-full" style={{ background: 'radial-gradient(circle,rgba(212,160,23,.28),transparent 70%)' }} aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-32 left-[32%] h-72 w-72 rounded-full" style={{ background: 'radial-gradient(circle,rgba(37,99,235,.3),transparent 70%)' }} aria-hidden="true" />
      <div className="relative z-[2]">
        <h1 className="mb-2 font-sans text-[28px] font-extrabold leading-[1.05] tracking-[-0.03em] sm:text-[34px]">Mutual Fund Rankings</h1>
        <p className="mb-5 max-w-[600px] text-small leading-relaxed text-slate-300 sm:text-body">
          Discover India’s highest-rated mutual funds using DhanRadar Intelligence — best funds first, every question answered.
        </p>
        <div className="grid grid-cols-3 gap-px overflow-hidden rounded-xl bg-white/10 lg:grid-cols-6">
          {kpis.map((k) => {
            const inner = (
              <>
                <div className="text-[9.5px] font-semibold uppercase leading-tight tracking-wide text-slate-400">{k.label}</div>
                <div className="mt-1 font-sans font-extrabold leading-tight" style={{ fontSize: k.small ? 14 : 19, color: k.valueColor }}>
                  {k.value}{k.sub && <span className="ml-1 text-[11px] font-semibold opacity-85">{k.sub}</span>}
                </div>
              </>
            );
            return k.href ? (
              <Link key={k.label} href={k.href} className="block bg-white/[0.04] px-3.5 py-3 transition-colors hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50">
                {inner}
              </Link>
            ) : (
              <div key={k.label} className="bg-white/[0.04] px-3.5 py-3">
                {inner}
              </div>
            );
          })}
        </div>
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {HERO_QUICK.map((t, i) => (
            <Link
              key={t.label}
              href={t.href}
              onClick={() => setActive(i)}
              className={cn(
                'shrink-0 whitespace-nowrap rounded-xl border px-3.5 py-2 text-caption font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50',
                active === i ? 'border-white bg-white text-navy' : 'border-white/20 bg-white/10 text-white hover:bg-white/20',
              )}
            >
              {t.label}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Sticky category nav
// ═══════════════════════════════════════════════════════════════════════════
export function CatNav() {
  const [active, setActive] = React.useState('top100');
  const go = (id: string) => {
    setActive(id);
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  return (
    <div className="sticky top-0 z-20 -mx-4 mt-6 border-y border-line bg-surface/95 backdrop-blur sm:-mx-6">
      <div className="flex gap-1.5 overflow-x-auto px-4 py-2 [scrollbar-width:none] sm:px-6 [&::-webkit-scrollbar]:hidden">
        {CATNAV.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => go(c.id)}
            className={cn(
              'shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
              active === c.id ? 'bg-navy text-white' : 'text-ink-muted hover:bg-surface-2 hover:text-ink',
            )}
          >
            {c.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S2 — DISCOVERY SHORTCUTS
// ═══════════════════════════════════════════════════════════════════════════
export function DiscoverSection() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {DISC.map((d) => <DiscCard key={d.name} {...d} />)}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S3 — TOP 100  (compare tray lives here)
// ═══════════════════════════════════════════════════════════════════════════
const T100_TABS = [
  { key: '10', label: 'Top 10', limit: 10 },
  { key: '25', label: 'Top 25', limit: 25 },
  { key: '50', label: 'Top 50', limit: 50 },
  { key: '100', label: 'Top 100', limit: 100 },
];
const T100_COLS = ['#', 'Fund', 'Read', 'Risk', '3Y', '5Y', 'SIP', 'Cost', 'Size', 'Momentum', ''];

function medal(i: number) {
  return i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : null;
}

// Unified row shape the table/cards render from — sample (score-based ring) and
// live (label/band-based ring, no score) both normalise into this before JSX.
// `rank` = the fund's original board position (1-based) — client-side sort and
// filters (I4) reorder the display, but the shown rank/medal stays the board's.
type T100Row = {
  key: string; name: string; amc: string; cat: string; logo: string; color: string;
  ring: RingSpec; labelWord: string; labelColor: string; risk: string;
  r3: number | null; r5: number | null; sipWord: string; exp: number | null; aum: number | null;
  rankd: string; trend: 'up' | 'down' | 'flat'; href?: string; rank: number;
};

// I4 — Top-100 client-side filters (mobile FilterSheet). Every option maps to a
// REAL field on the live rows (same "a chip is a saved query or it does not
// exist" rule as quickIntents): category class prefix on sebi_category, the
// SEBI riskometer band string, or the page's educational label word.
export type T100Filters = { group?: string; risk?: string; label?: string };

// I4 — client-side sortable columns (desktop table headers). `best` = the sort
// direction that puts the conventionally-better value first on the FIRST click
// (higher returns / bigger AUM = -1 desc; lower cost = 1 asc).
type T100SortCol = 'r3' | 'r5' | 'exp' | 'aum';
const T100_SORTABLE: Record<string, { col: T100SortCol; best: 1 | -1 }> = {
  '3Y': { col: 'r3', best: -1 },
  '5Y': { col: 'r5', best: -1 },
  Cost: { col: 'exp', best: 1 },
  Size: { col: 'aum', best: -1 },
};

function sampleT100Row(fnd: Fund): Omit<T100Row, 'rank'> {
  const lbl = eduLabel(fnd.score);
  return {
    key: fnd.name, name: fnd.name, amc: fnd.amc, cat: fnd.cat, logo: fnd.logo, color: fnd.color,
    ring: { kind: 'score', score: fnd.score }, labelWord: lbl.word, labelColor: lbl.color,
    risk: fnd.risk, r3: fnd.r3, r5: fnd.r5, sipWord: STRENGTH_WORD[toStrength(fnd.sip)],
    exp: fnd.exp, aum: fnd.aum, rankd: fnd.rankd, trend: fnd.trend,
  };
}
function liveT100Row(r: LbFundRow): Omit<T100Row, 'rank'> {
  const name = fundName(r);
  const lbl = eduWordFromLabel(r.verb_label);
  const trend: T100Row['trend'] = (r.rank_delta ?? 0) > 0 ? 'up' : (r.rank_delta ?? 0) < 0 ? 'down' : 'flat';
  return {
    key: r.isin, name, amc: r.amc_name, cat: r.sebi_category, logo: initialOf(name), color: colorFor(r.isin),
    ring: { kind: 'band', band: r.confidence_band, color: lbl.color }, labelWord: lbl.word, labelColor: lbl.color,
    risk: r.riskometer ?? '—', r3: r.return_3y_pct, r5: r.return_5y_pct, sipWord: '—',
    exp: r.expense_ratio_pct, aum: r.aum_crore, rankd: fmtDelta(r.rank_delta), trend,
    href: `/mf/fund/${r.isin}`,
  };
}

export function Top100Section({ live, filters }: { live?: LbFundRow[]; filters?: T100Filters } = {}) {
  const router = useRouter();
  const [tab, setTab] = React.useState('10');
  const [mobileAll, setMobileAll] = React.useState(false);
  // I3 — selection keyed by row.key (the ISIN on live rows), never by render
  // index: sort/filter reorder the list, an index would silently swap the
  // selected funds. Cap 3 = the compare page's slot count (page.tsx slice(0,3)).
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [sort, setSort] = React.useState<{ col: T100SortCol; dir: 1 | -1 } | null>(null);
  // V4 — live row keys are ISINs; sample keys are names and never match.
  const pfIsins = React.useContext(PortfolioIsinsContext);

  if (live && live.length === 0) {
    return <EmptyState title="No ranked funds yet" description="Rankings refresh nightly after markets close — check back soon." />;
  }

  const master: T100Row[] = (live ? live.map(liveT100Row) : FUNDS.map(sampleT100Row))
    .map((r, i) => ({ ...r, rank: i + 1 }));
  // Filters only bite on live rows — sample rows carry preview-era category
  // strings the live vocabulary doesn't match (honest: preview doesn't filter).
  const filtered = live
    ? master.filter((r) =>
        (!filters?.group || r.cat.startsWith(filters.group)) &&
        (!filters?.risk || r.risk === filters.risk) &&
        (!filters?.label || r.labelWord === filters.label))
    : master;
  const limit = T100_TABS.find((t) => t.key === tab)!.limit;
  const list = filtered.slice(0, limit);
  if (sort) {
    list.sort((a, b) => {
      const av = a[sort.col], bv = b[sort.col];
      if (av == null && bv == null) return 0;
      if (av == null) return 1; // nulls always last, either direction
      if (bv == null) return -1;
      return (av - bv) * sort.dir;
    });
  }
  const mobileList = filtered.slice(0, mobileAll ? filtered.length : 8);

  const toggle = (key: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else if (next.size < 3) next.add(key);
      return next;
    });

  const headerSort = (label: string) => {
    const spec = T100_SORTABLE[label];
    if (!spec) return;
    setSort((prev) =>
      prev?.col === spec.col ? { col: spec.col, dir: -prev.dir as 1 | -1 } : { col: spec.col, dir: spec.best });
  };

  return (
    <>
      {/* tabs */}
      <div className="mb-3.5 flex gap-1.5">
        {T100_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              'rounded-lg border px-3.5 py-2 text-[12.5px] font-semibold shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
              tab === t.key ? 'border-navy bg-navy text-white' : 'border-line bg-surface text-ink-secondary hover:bg-surface-2',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* DESKTOP table */}
      <div className="hidden overflow-x-auto rounded-2xl border border-line bg-surface shadow-sm md:block">
        <table className="w-full min-w-[1040px] border-collapse text-small">
          <thead>
            <tr>
              {T100_COLS.map((c, i) => {
                const sortable = T100_SORTABLE[c];
                const active = sortable && sort?.col === sortable.col;
                return (
                  <th
                    key={i}
                    aria-sort={active ? (sort!.dir === 1 ? 'ascending' : 'descending') : undefined}
                    className={cn(
                      'sticky top-0 z-[2] border-b-2 border-line bg-surface-2 px-3.5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-ink-muted',
                      i < 2 ? 'text-left' : 'text-right',
                    )}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => headerSort(c)}
                        className={cn(
                          'inline-flex items-center gap-1 font-mono text-[10px] font-bold uppercase tracking-[0.04em] hover:text-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded',
                          active ? 'text-royal' : 'text-ink-muted',
                        )}
                      >
                        {c}
                        <span aria-hidden="true">{active ? (sort!.dir === 1 ? '▲' : '▼') : '↕'}</span>
                      </button>
                    ) : c}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {list.map((row) => {
              const up = row.trend === 'up', down = row.trend === 'down';
              return (
                <tr
                  key={row.key}
                  className={cn('hover:bg-surface-2', row.rank <= 3 && 'bg-amber/[0.08]', row.href && 'cursor-pointer')}
                  onClick={row.href ? () => router.push(row.href!) : undefined}
                >
                  <td className="border-b border-line px-3.5 py-2.5 text-left">
                    <span className="inline-flex w-10 items-center gap-1.5 font-sans text-base font-extrabold text-ink">
                      {medal(row.rank - 1) ?? `#${row.rank}`}
                    </span>
                  </td>
                  <td className="border-b border-line px-3.5 py-2.5 text-left">
                    <div className="flex min-w-[220px] items-center gap-2.5">
                      <Logo letter={row.logo} color={row.color} />
                      <div>
                        {row.href ? (
                          <Link href={row.href} onClick={(e) => e.stopPropagation()} className="block text-small font-bold leading-tight text-ink hover:text-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded">
                            {row.name}
                          </Link>
                        ) : (
                          <div className="text-small font-bold leading-tight text-ink">{row.name}</div>
                        )}
                        <div className="mt-0.5 text-[11px] font-medium text-ink-muted">
                          {row.amc} ·{' '}
                          {row.href ? (
                            <Link
                              href={`/mf/explore?category=${encodeURIComponent(row.cat)}`}
                              onClick={(e) => e.stopPropagation()}
                              className="hover:text-royal hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded"
                            >
                              {row.cat}
                            </Link>
                          ) : row.cat}
                          {pfIsins.has(row.key) && <PortfolioPill className="ml-1.5 align-middle" />}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="border-b border-line px-3.5 py-2.5 text-right">
                    <span className="inline-flex items-center justify-end gap-1.5"><RingCell ring={row.ring} /><EduPill word={row.labelWord} color={row.labelColor} /></span>
                  </td>
                  <td className="border-b border-line px-3.5 py-2.5 text-right"><RiskBadge risk={row.risk} /></td>
                  <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-bold text-emerald">{pctSigned(row.r3)}</td>
                  <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-bold text-emerald">{pctSigned(row.r5)}</td>
                  <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-bold text-ink">{row.sipWord}</td>
                  <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-bold text-ink">{ter1(row.exp)}</td>
                  <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-bold text-ink">{row.aum != null ? aum(row.aum) : '—'}</td>
                  <td className="border-b border-line px-3.5 py-2.5 text-right">
                    <span className="inline-flex items-center justify-end gap-1.5 font-mono font-bold" style={{ color: up ? E : down ? '#E5484D' : 'var(--text-muted)' }}>
                      {up ? '▲' : down ? '▼' : '–'} {row.rankd}
                      <MiniSpark seed={row.name.charCodeAt(0) * 5} up={!down} />
                    </span>
                  </td>
                  <td className="border-b border-line px-3.5 py-2.5 text-right">
                    <span className="inline-flex gap-1.5">
                      <IconBtn title="Compare" aria-pressed={selected.has(row.key)} onClick={(e) => { e.stopPropagation(); toggle(row.key); }}>
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4v16M20 4v16M9 8l-5 4 5 4M15 8l5 4-5 4" /></svg>
                      </IconBtn>
                      <IconBtn title="Watch">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3l2.5 6.5L21 10l-5 4.5L17.5 21 12 17l-5.5 4L8 14.5 3 10l6.5-.5z" /></svg>
                      </IconBtn>
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* MOBILE ranking cards */}
      <div className="md:hidden">
        {mobileList.map((row) => {
          const up = row.trend === 'up', down = row.trend === 'down';
          // ponytail: compare-toggle already owns the row tap; nesting a Link
          // inside a <button> is invalid HTML, so the wrapper becomes a
          // role="button" div (keyboard-equivalent) and the fund-name Link
          // (stopPropagation) is the accessible fund-page entry point.
          return (
            <div
              key={row.key}
              role="button"
              tabIndex={0}
              onClick={() => toggle(row.key)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(row.key); } }}
              className={cn(
                'mb-2 flex w-full cursor-pointer items-center gap-3 rounded-xl border border-line bg-surface p-3 text-left shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                row.rank <= 3 && 'bg-amber/[0.08]',
                selected.has(row.key) && 'ring-2 ring-royal/40',
              )}
            >
              <span className="w-7 shrink-0 text-center font-sans text-[17px] font-extrabold text-ink">{medal(row.rank - 1) ?? `#${row.rank}`}</span>
              <Logo letter={row.logo} color={row.color} size={38} radius={10} font={14} />
              <div className="min-w-0 flex-1">
                {row.href ? (
                  <Link href={row.href} onClick={(e) => e.stopPropagation()} className="block truncate text-small font-bold leading-tight text-ink hover:text-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded">
                    {row.name}
                  </Link>
                ) : (
                  <div className="truncate text-small font-bold leading-tight text-ink">{row.name}</div>
                )}
                <div className="mt-0.5 text-[10.5px] text-ink-muted">{row.amc} · {row.cat}</div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <EduPill word={row.labelWord} color={row.labelColor} />
                  {pfIsins.has(row.key) && <PortfolioPill />}
                  <span className="rounded px-1.5 py-0.5 text-[9px] font-bold" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>{pctSigned(row.r3)} 3Y</span>
                  <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[9px] font-bold" style={{ color: up ? E : down ? '#E5484D' : 'var(--text-muted)' }}>{up ? '▲' : down ? '▼' : '–'}{row.rankd}</span>
                </div>
              </div>
              <RingCell ring={row.ring} size={40} stroke={5} />
            </div>
          );
        })}
        <button
          type="button"
          onClick={() => setMobileAll((v) => !v)}
          className="w-full rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-small font-semibold text-ink transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
        >
          {mobileAll ? 'Show less' : 'Show Top 20'}
        </button>
      </div>

      <SoWhat>
        {live
          ? <RichText text="**Funds are ranked using the DhanRadar educational label and confidence band** — a band reflects data consistency and quality, not a promise of future returns. A high-return, high-risk fund can rank below a steadier one." />
          : <RichText text="**Parag Parikh Flexi Cap leads the board** — the highest blend of returns, consistency, low cost and manager quality. Funds are ranked on the DhanRadar Score, not just past returns, so a high-return-high-risk fund can rank below a steadier one." />}
      </SoWhat>

      <CompareTray master={master} selected={selected} live={!!live} onClear={() => setSelected(new Set())} />
    </>
  );
}

function CompareTray({ master, selected, live, onClear }: { master: T100Row[]; selected: Set<string>; live: boolean; onClear: () => void }) {
  const router = useRouter();
  if (selected.size === 0) return null;
  const rows = master.filter((r) => selected.has(r.key));
  // I3 — live row keys ARE ISINs (liveT100Row: key = r.isin); sample keys are
  // fund names, so preview mode keeps the CTA disabled (same "only LIVE rows
  // deep-link" rule as every other board link).
  const isins = live ? rows.map((r) => r.key) : [];
  return (
    <div className="fixed bottom-5 left-1/2 z-30 flex -translate-x-1/2 items-center gap-3.5 rounded-2xl bg-navy px-4 py-3 text-white shadow-lg">
      <span className="text-[12.5px] font-bold">{selected.size} selected</span>
      <div className="flex">
        {rows.map((r, k) => (
          <span key={r.key} className="grid h-[30px] w-[30px] place-items-center rounded-lg font-sans text-[11px] font-extrabold text-white" style={{ background: r.color, border: '2px solid #0B1F3A', marginLeft: k === 0 ? 0 : -8 }}>
            {r.logo}
          </span>
        ))}
      </div>
      <button
        type="button"
        disabled={isins.length === 0}
        title={isins.length === 0 ? 'Compare opens with live fund data' : undefined}
        onClick={isins.length > 0 ? () => router.push(`/mf/compare?funds=${isins.join(',')}`) : undefined}
        className={cn('rounded-lg bg-royal px-3.5 py-2 text-xs font-bold text-white', isins.length === 0 && 'cursor-not-allowed opacity-50')}
      >
        Compare →
      </button>
      <button type="button" onClick={onClear} className="rounded-lg bg-white/10 px-3.5 py-2 text-xs font-bold text-white">Clear</button>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S4 — CATEGORY CHAMPIONS  (grid on lg, rail on mobile)
// ═══════════════════════════════════════════════════════════════════════════
type ChampView = {
  key: string; cat: string; winner: string; wLogo: string; wColor: string; ring: RingSpec;
  ret: string; runner: string; rLogo: string; rColor: string; why: string;
  wHref?: string; rHref?: string; catHref?: string;
};
function sampleChampView(c: typeof CHAMP[number]): ChampView {
  return {
    key: c.cat + c.winner, cat: c.cat, winner: c.winner, wLogo: c.wLogo, wColor: c.wColor,
    ring: { kind: 'score', score: c.score }, ret: c.ret, runner: c.runner, rLogo: c.rLogo, rColor: c.rColor, why: c.why,
  };
}
function liveChampView(c: LbChampionRow): ChampView {
  const wName = fundName(c.winner);
  const rName = c.runner_up ? fundName(c.runner_up) : '—';
  const lbl = eduWordFromLabel(c.winner.verb_label);
  return {
    key: c.category, cat: c.category, winner: wName, wLogo: initialOf(wName), wColor: colorFor(c.winner.isin),
    ring: { kind: 'band', band: c.winner.confidence_band, color: lbl.color },
    ret: `${pct1(c.winner.return_3y_pct)} 3Y`, runner: rName,
    rLogo: c.runner_up ? initialOf(rName) : '·', rColor: c.runner_up ? colorFor(c.runner_up.isin) : 'var(--surface-3)',
    why: c.why,
    wHref: `/mf/fund/${c.winner.isin}`,
    rHref: c.runner_up ? `/mf/fund/${c.runner_up.isin}` : undefined,
    catHref: `/mf/explore?category=${encodeURIComponent(c.category)}`,
  };
}
function ChampCard({ c, rail = false }: { c: ChampView; rail?: boolean }) {
  return (
    <div className={cn('rounded-xl border border-line bg-surface p-4 shadow-sm', rail && 'w-60 shrink-0')} style={rail ? { scrollSnapAlign: 'start' } : undefined}>
      <div className="flex items-center justify-between font-mono text-[9.5px] font-bold uppercase tracking-[0.04em] text-ink-muted">
        <span>🏆 {c.catHref ? <Link href={c.catHref} className="hover:text-royal hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded">{c.cat}</Link> : c.cat}</span>
        <span className="cursor-pointer text-royal">More →</span>
      </div>
      <div className="my-3 flex items-center gap-2.5 rounded-xl bg-amber/[0.14] p-2.5">
        <Logo letter={c.wLogo} color={c.wColor} />
        <div className="min-w-0">
          {c.wHref ? (
            <Link href={c.wHref} className="block truncate text-[12.5px] font-bold leading-tight text-ink hover:text-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded">{c.winner}</Link>
          ) : (
            <div className="truncate text-[12.5px] font-bold leading-tight text-ink">{c.winner}</div>
          )}
          <div className="text-[10px] text-ink-muted">Winner · {c.ret}</div>
        </div>
        <span className="ml-auto shrink-0"><RingCell ring={c.ring} size={28} stroke={4} /></span>
      </div>
      <div className="flex items-center gap-2.5 px-2.5 py-1 text-[11.5px] text-ink-secondary">
        <span className="grid h-[22px] w-[22px] shrink-0 place-items-center rounded-md font-sans text-[9px] font-extrabold text-white" style={{ background: c.rColor }}>{c.rLogo}</span>
        Runner-up · {c.rHref ? <Link href={c.rHref} className="hover:text-royal hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded">{c.runner}</Link> : c.runner}
      </div>
      <div className="mt-2.5 flex gap-1.5 border-t border-dashed border-line pt-2.5 text-[10.5px] leading-snug text-ink-muted">
        <span className="shrink-0 font-extrabold text-emerald" aria-hidden="true">✓</span>
        <span>{c.why}</span>
      </div>
    </div>
  );
}
export function ChampionsSection({ live }: { live?: LbChampionRow[] } = {}) {
  if (live && live.length === 0) {
    return <EmptyState title="No category champions yet" description="Champions publish once a category has enough ranked funds." />;
  }
  const champs: ChampView[] = live ? live.map(liveChampView) : CHAMP.map(sampleChampView);
  return (
    <>
      {/* desktop grid */}
      <div className="hidden gap-3 sm:grid sm:grid-cols-2 lg:grid-cols-4">
        {champs.map((c) => <ChampCard key={c.key} c={c} />)}
      </div>
      {/* mobile rail */}
      <div className="sm:hidden">
        <HScroll>{champs.map((c) => <ChampCard key={c.key} c={c} rail />)}</HScroll>
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Generic rail section (Performance / SIP / Risk / Value / Intelligence / Flows / Improved / Trending)
// ═══════════════════════════════════════════════════════════════════════════
export function RailSection({ rails }: { rails: Rail[] }) {
  return <HScroll>{rails.map((r) => <MiniLbCard key={r.title + r.icon} rail={r} />)}</HScroll>;
}

// S9 — full coverage (all 5 rails live) → section badge (intelLive in page.tsx);
// any subset live → per-rail chip (coverageRail pattern, same as Performance/Risk).
export function IntelligenceSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const allLive = !!(boards?.hidden_gems && boards?.future_leaders && boards?.momentum && boards?.quality && boards?.ai_spotlight);
  const rails: Rail[] = [
    coverageRail(allLive, INTEL_RAIL[0], boards?.hidden_gems, (r) => fundRailRow(r, 'Gem', true)),
    coverageRail(allLive, INTEL_RAIL[1], boards?.future_leaders, (r) => fundRailRow(r, fmtDelta(r.metric_value), true)),
    coverageRail(allLive, INTEL_RAIL[2], boards?.momentum, (r) => fundRailRow(r, fmtDelta(r.metric_value), true)),
    coverageRail(allLive, INTEL_RAIL[3], boards?.quality, (r) => fundRailRow(r, r.metric_value != null ? r.metric_value.toFixed(2) : '—', true)),
    coverageRail(allLive, INTEL_RAIL[4], boards?.ai_spotlight, (r) => fundRailRow(r, r.metric_value != null ? `In ${r.metric_value} boards` : '—', true)),
  ];
  const takeaway = boards?.momentum?.takeaway;
  return (
    <>
      <RailSection rails={rails} />
      {takeaway && <SoWhat><LiveBadge className="mr-1.5 align-middle" /><RichText text={takeaway} /></SoWhat>}
    </>
  );
}

// S5 — full coverage (perf_1y/3y/5y + wealth_creator all live) → section badge;
// any subset live → per-rail chip (coverageRail, page.tsx computes the same allLive).
export function PerformanceSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const allLive = !!(boards?.perf_1y && boards?.perf_3y && boards?.perf_5y && boards?.wealth_creator);
  const rails: Rail[] = [
    coverageRail(allLive, PERF_RAIL[0], boards?.perf_1y, (r) => fundRailRow(r, pctSigned(r.return_1y_pct), (r.return_1y_pct ?? 0) >= 0, r.metric_category_avg)),
    coverageRail(allLive, PERF_RAIL[1], boards?.perf_3y, (r) => fundRailRow(r, pctSigned(r.return_3y_pct), (r.return_3y_pct ?? 0) >= 0, r.metric_category_avg)),
    coverageRail(allLive, PERF_RAIL[2], boards?.perf_5y, (r) => fundRailRow(r, pctSigned(r.return_5y_pct), (r.return_5y_pct ?? 0) >= 0, r.metric_category_avg)),
    coverageRail(allLive, PERF_RAIL[3], boards?.wealth_creator, (r) => fundRailRow(r, metricVal(r), true)),
  ];
  const takeaway = boards?.perf_3y?.takeaway;
  return (
    <>
      <RailSection rails={rails} />
      {takeaway && <SoWhat><LiveBadge className="mr-1.5 align-middle" /><RichText text={takeaway} /></SoWhat>}
    </>
  );
}

// S6 — all 4 rails wired (sip_beginner = D4 published-rule rail, signed off
// 2026-08-16) → per-rail chip when coverage is mixed.
export function SipSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const rails: Rail[] = [
    liveRail(SIP_RAIL[0], boards?.sip_3y, (r) => fundRailRow(r, sipXirrVal(r), undefined, r.metric_category_avg)),
    liveRail(SIP_RAIL[1], boards?.sip_5y, (r) => fundRailRow(r, sipXirrVal(r), undefined, r.metric_category_avg)),
    liveRail(SIP_RAIL[2], boards?.sip_consistency, (r) => fundRailRow(r, sipConsistencyWord(r))),
    liveRail(SIP_RAIL[3], boards?.sip_beginner, (r) => fundRailRow(r, sipXirrVal(r), undefined, r.metric_category_avg)),
  ];
  const takeaway = boards?.sip_3y?.takeaway;
  return (
    <>
      <RailSection rails={rails} />
      {takeaway && <SoWhat><LiveBadge className="mr-1.5 align-middle" /><RichText text={takeaway} /></SoWhat>}
    </>
  );
}

// S7 — full coverage (risk_lowest/drawdown/sharpe + risk_recovery all live) →
// section badge; any subset live → per-rail chip. Same allLive treatment as
// PerformanceSection (page.tsx computes the matching boolean for the header).
export function RiskSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const allLive = !!(boards?.risk_lowest && boards?.risk_drawdown && boards?.risk_sharpe && boards?.risk_recovery);
  const rails: Rail[] = [
    coverageRail(allLive, RISK_RAIL[0], boards?.risk_lowest, (r) => fundRailRow(r, r.riskometer ?? '—', false)),
    // max_drawdown_pct is a POSITIVE magnitude on the wire — display as a fall ('−8.0%').
    coverageRail(allLive, RISK_RAIL[1], boards?.risk_drawdown, (r) => fundRailRow(r, r.max_drawdown_pct != null ? `−${r.max_drawdown_pct.toFixed(1)}%` : '—', false)),
    coverageRail(allLive, RISK_RAIL[2], boards?.risk_sharpe, (r) => fundRailRow(r, r.sharpe_ratio != null ? r.sharpe_ratio.toFixed(2) : '—', true)),
    coverageRail(allLive, RISK_RAIL[3], boards?.risk_recovery, (r) => fundRailRow(r, recoveryMonths(r), true)),
  ];
  const takeaway = boards?.risk_drawdown?.takeaway;
  return (
    <>
      <RailSection rails={rails} />
      {takeaway && <SoWhat><LiveBadge className="mr-1.5 align-middle" /><RichText text={takeaway} /></SoWhat>}
    </>
  );
}

// S8 — full coverage (all 3 value rails live) → section-level badge, no per-rail chip.
export function ValueSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const rails: Rail[] = [
    wiredRail(VALUE_RAIL[0], boards?.value_ter, (r) => fundRailRow(r, ter1(r.expense_ratio_pct), false, r.metric_category_avg)),
    wiredRail(VALUE_RAIL[1], boards?.value_efficiency, (r) => fundRailRow(r, metricVal(r), true)),
    wiredRail(VALUE_RAIL[2], boards?.value_index, (r) => fundRailRow(r, ter1(r.expense_ratio_pct), false, r.metric_category_avg)),
  ];
  const takeaway = boards?.value_ter?.takeaway;
  return (
    <>
      <RailSection rails={rails} />
      <ThreeLensCard board={boards?.three_lens} />
      {takeaway && <SoWhat><LiveBadge className="mr-1.5 align-middle" /><RichText text={takeaway} /></SoWhat>}
    </>
  );
}

// V3 (founder 2026-08-16) — ADDITIVE three-lenses view; the value rails above
// stay. One row per fund with return / deepest fall / cost side by side — the
// insight is the trade-off (strong-on-all-three is rare). Published rule in
// the caption; label + band only, no composite anywhere (non-neg #1/#2).
const THREE_LENS_RULE =
  'How this list is built: active growth funds in the top quarter of their own category on all three lenses at once — 3-year return, deepest fall, and cost — shown by highest 3-year return. Categories need at least 8 funds with all three measured.';

function ThreeLensCard({ board }: { board?: LbBoard<LbFundRow> }) {
  const rows = board?.rows ?? [];
  return (
    <Card className="mt-3.5 p-4">
      <div className="mb-1 flex items-center gap-2">
        <h3 className="font-sans text-[15px] font-bold text-ink">Strong on All Three Lenses</h3>
        {rows.length > 0 && <LiveBadge />}
      </div>
      <p className="mb-3 text-[11px] leading-relaxed text-ink-muted">{THREE_LENS_RULE}</p>
      {rows.length === 0 ? (
        <EmptyState title="No qualifying funds yet" description="This list publishes after the nightly refresh once category quartiles are computed." />
      ) : (
        <div className="grid gap-2">
          {rows.map((r) => {
            const name = fundName(r);
            return (
              <Link
                key={r.isin}
                href={`/mf/fund/${r.isin}`}
                className="grid grid-cols-1 items-center gap-2 rounded-xl border border-line bg-surface-2 p-3 transition-colors hover:border-royal/50 hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 sm:grid-cols-[minmax(200px,1.4fr)_repeat(3,1fr)]"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <Logo letter={initialOf(name)} color={colorFor(r.isin)} />
                  <div className="min-w-0">
                    <div className="truncate text-small font-bold text-ink">{name}</div>
                    <div className="truncate text-[10.5px] text-ink-muted">{r.sebi_category}</div>
                  </div>
                </div>
                {([
                  ['Return · 3Y', pctSigned(r.return_3y_pct), E],
                  ['Deepest fall', r.max_drawdown_pct != null ? `−${r.max_drawdown_pct.toFixed(1)}%` : '—', 'var(--text-primary)'],
                  ['Cost / yr', ter1(r.expense_ratio_pct), 'var(--text-primary)'],
                ] as const).map(([lens, val, color]) => (
                  <div key={lens} className="flex items-baseline justify-between gap-2 sm:block sm:text-right">
                    <span className="font-mono text-[9.5px] font-bold uppercase tracking-[0.04em] text-ink-muted">{lens}</span>
                    <div className="font-mono text-[13px] font-bold" style={{ color }}>{val}</div>
                  </div>
                ))}
              </Link>
            );
          })}
        </div>
      )}
    </Card>
  );
}

/** V6 — short static explainer for a category-inflow row, by category-name
 *  pattern. Factual/reviewed rule copy, never generated — matches the plan's
 *  "flow explainers" spec verbatim. Categories matching none of the patterns
 *  get no sub (rendered exactly as before). */
function flowCategorySub(category: string): string | undefined {
  if (/Arbitrage|Liquid|Overnight|Money Market/i.test(category)) return 'often used to park cash';
  if (/Small Cap|Mid Cap/i.test(category)) return 'higher risk appetite';
  if (/Index/i.test(category)) return 'shift to passive';
  if (/ELSS/i.test(category)) return 'tax-season flows';
  return undefined;
}

// S11 — rail 1 retitled to real category-level inflows (fund-level flows don't
// exist by design); rail 2 = aum_growth; rail 3 stays sample.
export function FlowsSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const rail1: Rail = boards?.category_inflows
    ? {
        title: 'Category Inflow Leaders', q: 'AMFI category-level net flow', icon: FLOW_RAIL[0].icon, color: FLOW_RAIL[0].color, live: true,
        rows: boards.category_inflows.rows.map((r): RailRow => {
          const val = `${r.net_flow_cr >= 0 ? '+' : '−'}${aum(Math.abs(r.net_flow_cr))}`;
          return {
            name: r.category, logo: initialOf(r.category), color: colorFor(r.category), val, up: r.net_flow_cr >= 0,
            href: `/mf/explore?category=${encodeURIComponent(r.category)}`,
            sub: flowCategorySub(r.category),
          };
        }),
      }
    : FLOW_RAIL[0];
  const rail2 = liveRail(FLOW_RAIL[1], boards?.aum_growth, (r) => fundRailRow(r, metricVal(r), true));
  const rails: Rail[] = [rail1, rail2, FLOW_RAIL[2]];
  const takeaway = boards?.category_inflows?.takeaway;
  return (
    <>
      <RailSection rails={rails} />
      {takeaway && <SoWhat><LiveBadge className="mr-1.5 align-middle" /><RichText text={takeaway} /></SoWhat>}
    </>
  );
}

// S12 — full coverage (movers_up + label_upgrades + top10_entries) → section badge.
// Rail 2 title is permanently 'Label Upgrades' (sampleData.ts) — numeric score
// deltas are forbidden, so live rows render a label transition instead.
export function ImprovedSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const rails: Rail[] = [
    wiredRail(IMPROVED_RAIL[0], boards?.movers_up, (r) => fundRailRow(r, fmtDelta(r.rank_delta), true)),
    wiredRail(IMPROVED_RAIL[1], boards?.label_upgrades, upgradeRailRow),
    wiredRail(IMPROVED_RAIL[2], boards?.top10_entries, (r) => fundRailRow(r, r.category_rank != null ? `#${r.category_rank}` : '—', true)),
  ];
  return <RailSection rails={rails} />;
}

// S16 — mixed coverage (movers_up/movers_down/aum_growth live, Investor Interest stays sample).
export function TrendingSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const rails: Rail[] = [
    liveRail(TREND_RAIL[0], boards?.movers_up, (r) => fundRailRow(r, fmtDelta(r.rank_delta), true)),
    liveRail(TREND_RAIL[1], boards?.movers_down, (r) => fundRailRow(r, fmtDelta(r.rank_delta), false)),
    liveRail(TREND_RAIL[2], boards?.aum_growth, (r) => fundRailRow(r, metricVal(r), true)),
    TREND_RAIL[3],
  ];
  return <RailSection rails={rails} />;
}

// ═══════════════════════════════════════════════════════════════════════════
// S10 — CURRENT MARKET (DMMI)
// ═══════════════════════════════════════════════════════════════════════════
function DmmiList({ rows }: { rows: { name: string; logo: string; color: string }[] }) {
  return (
    <div>
      {rows.map((r) => (
        <div key={r.name} className="flex items-center gap-2 py-1 text-[12px]">
          <span className="grid h-[22px] w-[22px] shrink-0 place-items-center rounded-md font-sans text-[9px] font-extrabold text-white" style={{ background: r.color }}>{r.logo}</span>
          <span className="flex-1 font-semibold text-ink-secondary">{r.name}</span>
        </div>
      ))}
    </div>
  );
}
export function MarketSection({ regime }: { regime?: string } = {}) {
  const regimeNote = regime ? REGIME_EXPLAINER[regime] : undefined;
  const blocks: { label: string; color: string; rows: typeof DMMI.best }[] = [
    { label: 'Best funds for now', color: 'var(--emerald)', rows: DMMI.best },
    { label: 'Best SIP today', color: 'var(--royal)', rows: DMMI.sip },
    { label: 'Best lumpsum today', color: 'var(--amber)', rows: DMMI.lump },
    { label: 'Out of favour now', color: 'var(--red)', rows: DMMI.out },
  ];
  return (
    <Card className="p-5">
      <div className="grid items-center gap-6 lg:grid-cols-[230px_1fr]">
        <div className="text-center">
          <Semicircle val={DMMI.value} />
          <div className="font-sans text-xl font-extrabold text-amber">{DMMI.mood}</div>
          <div className="mt-0.5 text-[11.5px] text-ink-muted">{DMMI.phase}</div>
          <div className="mt-2.5">
            <span className="rounded-lg bg-royal/[0.08] px-3 py-1.5 font-mono text-[11px] font-bold text-royal">{DMMI.strategy}</span>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {blocks.map((bl) => (
            <div key={bl.label} className="rounded-xl border border-line p-3.5">
              <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.03em]" style={{ color: bl.color }}>{bl.label}</div>
              <DmmiList rows={bl.rows} />
            </div>
          ))}
        </div>
      </div>
      <div className="mt-3.5">
        <Link href="/mood" className="inline-flex items-center gap-1 text-[12.5px] font-semibold text-royal hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded">
          Explore Market Mood →
        </Link>
      </div>
      <SoWhat>
        <RichText text="**Market mood is Cautiously Optimistic — typical phase: accumulation.** In similar phases, Flexi Cap & quality Small Cap funds led. This is an educational read of conditions, not a recommendation." />
      </SoWhat>
      {regimeNote && <p className="mt-3 text-caption leading-relaxed text-ink-muted">{regimeNote}</p>}
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S13 — MANAGERS  (table on lg, list on mobile)
// ═══════════════════════════════════════════════════════════════════════════
function ScoreWord({ score }: { score: number }) {
  const s = toStrength(score);
  return <span className="font-mono font-extrabold" style={{ color: STRENGTH_COLOR[s] }}>{STRENGTH_WORD[s]}</span>;
}
// Live rows carry no composite manager score, no third-party star rating, and no
// 'years beating benchmark'/'success %' figures (those don't exist on the live
// contract) — Quality reuses the AMC QualityCell word style (Strong=emerald,
// Good=cyan, Fair=amber) off percentile_word; Yrs Beating/Success/Rating render
// '—', same "no live equivalent" convention as AmcSection's Confidence/Trust.
const PCTL_WORD_COLOR: Record<string, string> = { Strong: E, Good: COLORS.C, Fair: COLORS.A };
type MgrRow = {
  key: string; name: string; amc: string | null; av: string; color: string;
  exp: string; funds: string; quality: QualitySpec; beating: string; success: string;
  topFund: string; rating: string;
};
function sampleMgrRow(m: typeof MGR[number]): MgrRow {
  return {
    key: m.name, name: m.name, amc: null, av: m.av, color: m.color,
    exp: m.exp, funds: m.funds, quality: { kind: 'score', score: m.score },
    beating: m.beating, success: m.success, topFund: m.topFund, rating: m.rating,
  };
}
function liveMgrRow(r: LbManagerRow): MgrRow {
  return {
    key: r.manager_name, name: r.manager_name, amc: r.amc_name, av: initialOf(r.manager_name), color: colorFor(r.manager_name),
    exp: `${Math.round(r.tenure_years)} yrs`, funds: `${r.funds_count} funds`,
    quality: { kind: 'word', word: r.percentile_word, color: PCTL_WORD_COLOR[r.percentile_word] ?? COLORS.A },
    beating: '—', success: '—', topFund: r.top_fund_name, rating: '—',
  };
}
export function ManagersSection({ live }: { live?: LbManagerRow[] } = {}) {
  if (live && live.length === 0) {
    return <EmptyState title="No manager data yet" description="Manager facts publish once the nightly refresh has enough covered schemes." />;
  }
  const rows: MgrRow[] = live ? live.map(liveMgrRow) : MGR.map(sampleMgrRow);
  return (
    <>
      {/* desktop table */}
      <Card className="hidden overflow-hidden lg:block">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-small">
            <thead>
              <tr>
                {['#', 'Manager', 'Experience', 'Funds', 'Quality', 'Yrs Beating', 'Success', 'Top Fund', 'Rating'].map((h, i) => (
                  <th key={h} className={cn('border-b-2 border-line bg-surface-2 px-3.5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-ink-muted', i < 2 ? 'text-left' : 'text-right')}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((m, i) => (
                <tr key={m.key}>
                  <td className="border-b border-line px-3.5 py-3 text-left font-sans font-extrabold text-ink-muted">{i + 1}</td>
                  <td className="border-b border-line px-3.5 py-3 text-left">
                    <div className="flex items-center gap-2.5">
                      <span className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-full font-sans text-xs font-bold text-white" style={{ background: m.color }}>{m.av}</span>
                      <div>
                        <div className="font-medium text-ink">{m.name}</div>
                        {m.amc && <div className="mt-0.5 text-[11px] font-medium text-ink-muted">{m.amc}</div>}
                      </div>
                    </div>
                  </td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono">{m.exp}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono">{m.funds}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right"><QualityCell quality={m.quality} /></td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono">{m.beating}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono text-emerald">{m.success}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right text-ink-secondary">{m.topFund}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right tracking-[1px] text-amber">{m.rating}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      {/* mobile list */}
      <Card className="p-4 lg:hidden">
        {rows.map((m, i) => (
          <div key={m.key} className="flex items-center gap-3 border-b border-line py-3 last:border-b-0">
            <span className="w-4 shrink-0 font-sans font-extrabold text-ink-muted">{i + 1}</span>
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full font-sans text-xs font-bold text-white" style={{ background: m.color }}>{m.av}</span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-small font-bold text-ink">{m.name}</div>
              <div className="truncate text-[10.5px] text-ink-muted">{m.amc ? `${m.amc} · ` : ''}{m.exp} · {m.topFund}</div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-[15px]"><QualityCell quality={m.quality} /></div>
              <div className="text-[11px] tracking-[0.5px] text-amber">{m.rating}</div>
            </div>
          </div>
        ))}
      </Card>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S14 — AMC  (table on lg, list on mobile)
// ═══════════════════════════════════════════════════════════════════════════
// Live rows carry no composite AMC score and no third-party stars (non-neg #2)
// — Quality renders the top-quartile-share WORD instead of ScoreWord, and
// Confidence/Trust (fields the live contract doesn't provide) render '—'.
type QualitySpec = { kind: 'score'; score: number } | { kind: 'word'; word: string; color: string };
function QualityCell({ quality }: { quality: QualitySpec }) {
  return quality.kind === 'score'
    ? <ScoreWord score={quality.score} />
    : <span className="font-mono font-extrabold" style={{ color: quality.color }}>{quality.word}</span>;
}
type AmcRow = {
  key: string; name: string; av: string; color: string; quality: QualitySpec;
  topFunds: number; confidence: string; aum: string; age: string; indexFunds: number; trust: string;
};
function sampleAmcRow(m: typeof AMC[number]): AmcRow {
  return {
    key: m.name, name: m.name, av: m.av, color: m.color, quality: { kind: 'score', score: m.score },
    topFunds: m.topFunds, confidence: m.confidence, aum: m.aum, age: m.age, indexFunds: m.indexFunds, trust: m.trust,
  };
}
function liveAmcRow(r: LbAmcFactRow): AmcRow {
  const share = r.fund_count > 0 ? r.top_quartile_count / r.fund_count : 0;
  const word = share >= 0.3 ? 'Strong' : share >= 0.15 ? 'Good' : 'Fair';
  const color = share >= 0.3 ? E : share >= 0.15 ? COLORS.C : COLORS.A;
  const years = r.oldest_launch ? (Date.now() - new Date(r.oldest_launch).getTime()) / (1000 * 60 * 60 * 24 * 365.25) : null;
  return {
    key: r.amc_name, name: r.amc_name, av: initialOf(r.amc_name), color: colorFor(r.amc_name),
    quality: { kind: 'word', word, color },
    topFunds: r.top_quartile_count, confidence: '—',
    aum: r.aum_crore != null ? aum(r.aum_crore) : '—',
    age: years != null ? `${years.toFixed(0)} yrs` : '—',
    indexFunds: r.index_fund_count, trust: '—',
  };
}
export function AmcSection({ live }: { live?: LbAmcFactRow[] } = {}) {
  if (live && live.length === 0) {
    return <EmptyState title="No AMC data yet" description="AMC aggregates publish once the nightly refresh has ranked their funds." />;
  }
  const rows: AmcRow[] = live ? live.map(liveAmcRow) : AMC.map(sampleAmcRow);
  return (
    <>
      <Card className="hidden overflow-hidden lg:block">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-small">
            <thead>
              <tr>
                {['#', 'AMC', 'Quality', 'Top Funds', 'Confidence', 'AUM', 'Age', 'Index Funds', 'Trust'].map((h, i) => (
                  <th key={h} className={cn('border-b-2 border-line bg-surface-2 px-3.5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-ink-muted', i < 2 ? 'text-left' : 'text-right')}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((m, i) => (
                <tr key={m.key}>
                  <td className="border-b border-line px-3.5 py-3 text-left font-sans font-extrabold text-ink-muted">{i + 1}</td>
                  <td className="border-b border-line px-3.5 py-3 text-left">
                    <div className="flex items-center gap-2.5">
                      <Logo letter={m.av} color={m.color} />
                      {live ? (
                        <Link href={`/mf/explore?q=${encodeURIComponent(m.name)}`} className="font-medium text-ink hover:text-royal hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded">
                          {m.name}
                        </Link>
                      ) : (
                        <span className="font-medium text-ink">{m.name}</span>
                      )}
                    </div>
                  </td>
                  <td className="border-b border-line px-3.5 py-3 text-right"><QualityCell quality={m.quality} /></td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono">{m.topFunds}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono">{m.confidence}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono">{m.aum}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono">{m.age}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono">{m.indexFunds}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right tracking-[1px] text-amber">{m.trust}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card className="p-4 lg:hidden">
        {rows.map((m, i) => (
          <div key={m.key} className="flex items-center gap-3 border-b border-line py-3 last:border-b-0">
            <span className="w-4 shrink-0 font-sans font-extrabold text-ink-muted">{i + 1}</span>
            <Logo letter={m.av} color={m.color} size={36} radius={9} />
            <div className="min-w-0 flex-1">
              {live ? (
                <Link href={`/mf/explore?q=${encodeURIComponent(m.name)}`} className="block truncate text-small font-bold text-ink hover:text-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded">
                  {m.name}
                </Link>
              ) : (
                <div className="truncate text-small font-bold text-ink">{m.name}</div>
              )}
              <div className="text-[10.5px] text-ink-muted">AUM {m.aum}</div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-[15px]"><QualityCell quality={m.quality} /></div>
              <div className="text-[11px] tracking-[0.5px] text-amber">{m.trust}</div>
            </div>
          </div>
        ))}
      </Card>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S15 — AI INSIGHTS (Trusted Ratings section removed — founder decision
// 2026-08-16: third-party ratings not required, no licensed source planned)
// ═══════════════════════════════════════════════════════════════════════════
export function AiInsightsSection({ live }: { live?: LbInsightRow[] }) {
  // Live cards from the governed gateway when the board exists; Preview sample otherwise.
  const texts = live && live.length > 0 ? live.map((r) => r.text) : AI_INSIGHTS;
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {texts.map((t, i) => (
        <div key={i} className="flex gap-3 rounded-xl border border-line p-3.5" style={{ background: 'linear-gradient(135deg,#FAFBFF,#fff)' }}>
          <span className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-lg" style={{ background: 'rgba(139,92,246,.10)', color: '#8B5CF6' }} aria-hidden="true">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3 L13.5 9 L19 10.5 L13.5 12 L12 18 L10.5 12 L5 10.5 L10.5 9 Z" /></svg>
          </span>
          <p className="m-0 text-small leading-relaxed text-ink-secondary"><RichText text={t} /></p>
        </div>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S17 — FAQ
// ═══════════════════════════════════════════════════════════════════════════
function FaqItem({ q, a, defaultOpen }: { q: string; a: string; defaultOpen?: boolean }) {
  const [open, setOpen] = React.useState(!!defaultOpen);
  return (
    <div className="border-b border-line last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 py-3.5 text-left text-small font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        {q}
        <span className={cn('shrink-0 text-ink-muted transition-transform', open && 'rotate-180')} aria-hidden="true">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 9 L12 15 L18 9" /></svg>
        </span>
      </button>
      {open && <p className="max-w-[880px] pb-4 text-small leading-relaxed text-ink-muted">{a}</p>}
    </div>
  );
}
export function FaqSection() {
  return (
    <Card className="px-5 py-1">
      {FAQ.map(([q, a], i) => <FaqItem key={q} q={q} a={a} defaultOpen={i === 0} />)}
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Mobile filter sheet (toolbar trigger lives in the page)
// ═══════════════════════════════════════════════════════════════════════════
// I4 — every option maps to a REAL field on the live Top-100 rows (no
// decorative chips): category class prefix, SEBI riskometer band, educational
// label word. Single-select per group; tapping the active option clears it.
const T100_SHEET_GROUPS: { title: string; key: keyof T100Filters; options: [string, string][] }[] = [
  {
    title: 'Category',
    key: 'group',
    options: [['Equity', 'Equity Scheme'], ['Hybrid', 'Hybrid Scheme'], ['Solution-Oriented', 'Solution Oriented Scheme']],
  },
  {
    title: 'Riskometer',
    key: 'risk',
    options: (['Low', 'Low to Moderate', 'Moderate', 'Moderately High', 'High', 'Very High'] as const).map((r) => [r, r]),
  },
  {
    title: 'Reading',
    key: 'label',
    options: (['In Form', 'On Track', 'Watch', 'Off Form'] as const).map((w) => [w, w]),
  },
];

export function FilterSheet({ open, onClose, value, onChange }: { open: boolean; onClose: () => void; value: T100Filters; onChange: (v: T100Filters) => void }) {
  return (
    <>
      <div className={cn('fixed inset-0 z-40 bg-black/50 transition-opacity md:hidden', open ? 'opacity-100' : 'pointer-events-none opacity-0')} onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Filter rankings"
        className={cn('fixed inset-x-0 bottom-0 z-50 mx-auto max-h-[86vh] max-w-[430px] overflow-y-auto rounded-t-[22px] bg-surface transition-transform duration-300 md:hidden', open ? 'translate-y-0' : 'translate-y-full')}
      >
        <div className="mx-auto mt-2.5 h-1 w-10 rounded-full bg-line-strong" />
        <div className="flex items-center border-b border-line px-[18px] pb-3 pt-1.5">
          <h3 className="flex-1 font-sans text-[17px] font-bold text-ink">Filter Rankings</h3>
          <CTA onClick={onClose}>Done</CTA>
        </div>
        <div className="px-[18px] py-4">
          <p className="mb-3 text-[11px] text-ink-muted">Filters apply to the Top 100 table.</p>
          {T100_SHEET_GROUPS.map(({ title, key, options }) => (
            <div key={title} className="mb-4">
              <h4 className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-ink-muted">{title}</h4>
              <div className="flex flex-wrap gap-1.5">
                {options.map(([label, optValue]) => {
                  const active = value[key] === optValue;
                  return (
                    <button
                      key={optValue}
                      type="button"
                      aria-pressed={active}
                      onClick={() => onChange({ ...value, [key]: active ? undefined : optValue })}
                      className={cn(
                        'rounded-lg border px-3 py-1.5 text-[11.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                        active ? 'border-royal bg-royal text-white' : 'border-line bg-surface-2 text-ink-secondary',
                      )}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        <div className="sticky bottom-0 flex gap-2.5 border-t border-line bg-surface px-[18px] py-3.5">
          <CTA variant="primary" className="flex-1" onClick={onClose}>Apply</CTA>
          <CTA onClick={() => onChange({})}>Reset</CTA>
        </div>
      </div>
    </>
  );
}

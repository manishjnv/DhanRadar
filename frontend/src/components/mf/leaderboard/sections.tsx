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
import { cn } from '@/lib/cn';
import {
  Logo, BandRing, BandRingLive, Semicircle, MiniSpark, EduPill, RiskBadge, Card, SoWhat,
  RichText, HScroll, IconBtn, CTA, DiscCard, MiniLbCard,
} from './ui';
import {
  COLORS, FUNDS, DISC, CHAMP, DMMI, MGR, AMC, RATINGS, AI_INSIGHTS, FAQ, CATNAV,
  HERO_KPIS, HERO_QUICK, FILTER_GROUPS,
  PERF_RAIL, SIP_RAIL, RISK_RAIL, VALUE_RAIL, INTEL_RAIL, FLOW_RAIL, IMPROVED_RAIL, TREND_RAIL,
  eduLabel, eduWordFromLabel, toStrength, STRENGTH_WORD, STRENGTH_COLOR, agreeBand, aum,
  type Fund, type Rail, type RailRow,
} from './sampleData';
import { EmptyState } from '@/components/ui/EmptyState';
import { LiveBadge } from '@/components/mf/funddetail/parts';
import type {
  LeaderboardHero, LeaderboardBoards,
  LbFundRow, LbChampionRow, LbLabelUpgradeRow, LbAmcFactRow,
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
function fundRailRow(r: LbFundRow, val: string, up?: boolean): RailRow {
  const name = fundName(r);
  return { name, logo: initialOf(name), color: colorFor(r.isin), val, up };
}
function upgradeRailRow(r: LbLabelUpgradeRow): RailRow {
  const name = fundName(r);
  const from = eduWordFromLabel(r.label_from).word;
  const to = eduWordFromLabel(r.label_to).word;
  return { name, logo: initialOf(name), color: colorFor(r.isin), val: `${from} → ${to}`, up: true };
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
  const kpis = hero ? [
    { label: 'Funds Ranked', value: hero.funds_ranked.toLocaleString('en-IN') },
    { label: 'Categories', value: String(hero.categories) },
    { label: 'Live Boards', value: String(hero.live_board_count) },
    { label: 'Top Rated Today', value: hero.top_fund ? (hero.top_fund.fund_name_short ?? hero.top_fund.scheme_name) : '—', small: true },
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
          Discover India’s highest-rated mutual funds using DhanRadar Intelligence and trusted industry ratings — best funds first, every question answered.
        </p>
        <div className="grid grid-cols-3 gap-px overflow-hidden rounded-xl bg-white/10 lg:grid-cols-6">
          {kpis.map((k) => (
            <div key={k.label} className="bg-white/[0.04] px-3.5 py-3">
              <div className="text-[9.5px] font-semibold uppercase leading-tight tracking-wide text-slate-400">{k.label}</div>
              <div className="mt-1 font-sans font-extrabold leading-tight" style={{ fontSize: k.small ? 14 : 19, color: k.valueColor }}>
                {k.value}{k.sub && <span className="ml-1 text-[11px] font-semibold opacity-85">{k.sub}</span>}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {HERO_QUICK.map((t, i) => (
            <button
              key={t}
              type="button"
              onClick={() => setActive(i)}
              className={cn(
                'shrink-0 whitespace-nowrap rounded-xl border px-3.5 py-2 text-caption font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50',
                active === i ? 'border-white bg-white text-navy' : 'border-white/20 bg-white/10 text-white hover:bg-white/20',
              )}
            >
              {t}
            </button>
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
  { key: '25', label: 'Top 25', limit: 20 },
  { key: '50', label: 'Top 50', limit: 20 },
  { key: '100', label: 'Top 100', limit: 20 },
];
const T100_COLS = ['#', 'Fund', 'Read', 'Risk', '3Y', '5Y', 'SIP', 'Cost', 'Size', 'Momentum', ''];

function medal(i: number) {
  return i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : null;
}

// Unified row shape the table/cards render from — sample (score-based ring) and
// live (label/band-based ring, no score) both normalise into this before JSX.
type T100Row = {
  key: string; name: string; amc: string; cat: string; logo: string; color: string;
  ring: RingSpec; labelWord: string; labelColor: string; risk: string;
  r3: number | null; r5: number | null; sipWord: string; exp: number | null; aum: number | null;
  rankd: string; trend: 'up' | 'down' | 'flat';
};
function sampleT100Row(fnd: Fund): T100Row {
  const lbl = eduLabel(fnd.score);
  return {
    key: fnd.name, name: fnd.name, amc: fnd.amc, cat: fnd.cat, logo: fnd.logo, color: fnd.color,
    ring: { kind: 'score', score: fnd.score }, labelWord: lbl.word, labelColor: lbl.color,
    risk: fnd.risk, r3: fnd.r3, r5: fnd.r5, sipWord: STRENGTH_WORD[toStrength(fnd.sip)],
    exp: fnd.exp, aum: fnd.aum, rankd: fnd.rankd, trend: fnd.trend,
  };
}
function liveT100Row(r: LbFundRow): T100Row {
  const name = fundName(r);
  const lbl = eduWordFromLabel(r.verb_label);
  const trend: T100Row['trend'] = (r.rank_delta ?? 0) > 0 ? 'up' : (r.rank_delta ?? 0) < 0 ? 'down' : 'flat';
  return {
    key: r.isin, name, amc: r.amc_name, cat: r.sebi_category, logo: initialOf(name), color: colorFor(r.isin),
    ring: { kind: 'band', band: r.confidence_band, color: lbl.color }, labelWord: lbl.word, labelColor: lbl.color,
    risk: r.riskometer ?? '—', r3: r.return_3y_pct, r5: r.return_5y_pct, sipWord: '—',
    exp: r.expense_ratio_pct, aum: r.aum_crore, rankd: fmtDelta(r.rank_delta), trend,
  };
}

export function Top100Section({ live }: { live?: LbFundRow[] } = {}) {
  const [tab, setTab] = React.useState('10');
  const [mobileAll, setMobileAll] = React.useState(false);
  const [selected, setSelected] = React.useState<Set<number>>(new Set());

  if (live && live.length === 0) {
    return <EmptyState title="No ranked funds yet" description="Rankings refresh nightly after markets close — check back soon." />;
  }

  const master: T100Row[] = live ? live.map(liveT100Row) : FUNDS.map(sampleT100Row);
  const limit = T100_TABS.find((t) => t.key === tab)!.limit;
  const list = master.slice(0, limit);
  const mobileList = master.slice(0, mobileAll ? master.length : 8);

  const toggle = (idx: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else if (next.size < 4) next.add(idx);
      return next;
    });

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
              {T100_COLS.map((c, i) => (
                <th
                  key={i}
                  className={cn(
                    'sticky top-0 z-[2] border-b-2 border-line bg-surface-2 px-3.5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-ink-muted',
                    i < 2 ? 'text-left' : 'text-right',
                  )}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {list.map((row, i) => {
              const up = row.trend === 'up', down = row.trend === 'down';
              return (
                <tr key={row.key} className={cn('hover:bg-surface-2', i < 3 && 'bg-amber/[0.08]')}>
                  <td className="border-b border-line px-3.5 py-2.5 text-left">
                    <span className="inline-flex w-10 items-center gap-1.5 font-sans text-base font-extrabold text-ink">
                      {medal(i) ?? `#${i + 1}`}
                    </span>
                  </td>
                  <td className="border-b border-line px-3.5 py-2.5 text-left">
                    <div className="flex min-w-[220px] items-center gap-2.5">
                      <Logo letter={row.logo} color={row.color} />
                      <div>
                        <div className="text-small font-bold leading-tight text-ink">{row.name}</div>
                        <div className="mt-0.5 text-[11px] font-medium text-ink-muted">{row.amc} · {row.cat}</div>
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
                      <IconBtn title="Compare" aria-pressed={selected.has(i)} onClick={() => toggle(i)}>
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
        {mobileList.map((row, i) => {
          const up = row.trend === 'up', down = row.trend === 'down';
          return (
            <button
              key={row.key}
              type="button"
              onClick={() => toggle(i)}
              className={cn(
                'mb-2 flex w-full items-center gap-3 rounded-xl border border-line bg-surface p-3 text-left shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                i < 3 && 'bg-amber/[0.08]',
                selected.has(i) && 'ring-2 ring-royal/40',
              )}
            >
              <span className="w-7 shrink-0 text-center font-sans text-[17px] font-extrabold text-ink">{medal(i) ?? `#${i + 1}`}</span>
              <Logo letter={row.logo} color={row.color} size={38} radius={10} font={14} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-small font-bold leading-tight text-ink">{row.name}</div>
                <div className="mt-0.5 text-[10.5px] text-ink-muted">{row.amc} · {row.cat}</div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <EduPill word={row.labelWord} color={row.labelColor} />
                  <span className="rounded px-1.5 py-0.5 text-[9px] font-bold" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>{pctSigned(row.r3)} 3Y</span>
                  <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[9px] font-bold" style={{ color: up ? E : down ? '#E5484D' : 'var(--text-muted)' }}>{up ? '▲' : down ? '▼' : '–'}{row.rankd}</span>
                </div>
              </div>
              <RingCell ring={row.ring} size={40} stroke={5} />
            </button>
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

      <CompareTray master={master} selected={selected} onClear={() => setSelected(new Set())} />
    </>
  );
}

function CompareTray({ master, selected, onClear }: { master: T100Row[]; selected: Set<number>; onClear: () => void }) {
  if (selected.size === 0) return null;
  return (
    <div className="fixed bottom-5 left-1/2 z-30 flex -translate-x-1/2 items-center gap-3.5 rounded-2xl bg-navy px-4 py-3 text-white shadow-lg">
      <span className="text-[12.5px] font-bold">{selected.size} selected</span>
      <div className="flex">
        {[...selected].map((i, k) => (
          <span key={i} className="grid h-[30px] w-[30px] place-items-center rounded-lg font-sans text-[11px] font-extrabold text-white" style={{ background: master[i].color, border: '2px solid #0B1F3A', marginLeft: k === 0 ? 0 : -8 }}>
            {master[i].logo}
          </span>
        ))}
      </div>
      <button type="button" className="rounded-lg bg-royal px-3.5 py-2 text-xs font-bold text-white">Compare →</button>
      <button type="button" className="rounded-lg bg-white/10 px-3.5 py-2 text-xs font-bold text-white">★ Watchlist</button>
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
  };
}
function ChampCard({ c, rail = false }: { c: ChampView; rail?: boolean }) {
  return (
    <div className={cn('rounded-xl border border-line bg-surface p-4 shadow-sm', rail && 'w-60 shrink-0')} style={rail ? { scrollSnapAlign: 'start' } : undefined}>
      <div className="flex items-center justify-between font-mono text-[9.5px] font-bold uppercase tracking-[0.04em] text-ink-muted">
        <span>🏆 {c.cat}</span>
        <span className="cursor-pointer text-royal">More →</span>
      </div>
      <div className="my-3 flex items-center gap-2.5 rounded-xl bg-amber/[0.14] p-2.5">
        <Logo letter={c.wLogo} color={c.wColor} />
        <div className="min-w-0">
          <div className="truncate text-[12.5px] font-bold leading-tight text-ink">{c.winner}</div>
          <div className="text-[10px] text-ink-muted">Winner · {c.ret}</div>
        </div>
        <span className="ml-auto shrink-0"><RingCell ring={c.ring} size={28} stroke={4} /></span>
      </div>
      <div className="flex items-center gap-2.5 px-2.5 py-1 text-[11.5px] text-ink-secondary">
        <span className="grid h-[22px] w-[22px] shrink-0 place-items-center rounded-md font-sans text-[9px] font-extrabold text-white" style={{ background: c.rColor }}>{c.rLogo}</span>
        Runner-up · {c.runner}
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

// Untouched — S9 Intelligence extras are not wired this session.
export const IntelligenceSection = () => <RailSection rails={INTEL_RAIL} />;

// S5 — full coverage (perf_1y/3y/5y + wealth_creator all live) → section badge;
// any subset live → per-rail chip (coverageRail, page.tsx computes the same allLive).
export function PerformanceSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const allLive = !!(boards?.perf_1y && boards?.perf_3y && boards?.perf_5y && boards?.wealth_creator);
  const rails: Rail[] = [
    coverageRail(allLive, PERF_RAIL[0], boards?.perf_1y, (r) => fundRailRow(r, pctSigned(r.return_1y_pct), (r.return_1y_pct ?? 0) >= 0)),
    coverageRail(allLive, PERF_RAIL[1], boards?.perf_3y, (r) => fundRailRow(r, pctSigned(r.return_3y_pct), (r.return_3y_pct ?? 0) >= 0)),
    coverageRail(allLive, PERF_RAIL[2], boards?.perf_5y, (r) => fundRailRow(r, pctSigned(r.return_5y_pct), (r.return_5y_pct ?? 0) >= 0)),
    coverageRail(allLive, PERF_RAIL[3], boards?.wealth_creator, (r) => fundRailRow(r, metricVal(r), true)),
  ];
  return <RailSection rails={rails} />;
}

// S6 — mixed coverage (sip_3y/sip_5y/sip_consistency live, Best SIP for
// Beginners stays sample — founder decision D4 pending) → per-rail chip.
export function SipSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const rails: Rail[] = [
    liveRail(SIP_RAIL[0], boards?.sip_3y, (r) => fundRailRow(r, sipXirrVal(r))),
    liveRail(SIP_RAIL[1], boards?.sip_5y, (r) => fundRailRow(r, sipXirrVal(r))),
    liveRail(SIP_RAIL[2], boards?.sip_consistency, (r) => fundRailRow(r, sipConsistencyWord(r))),
    SIP_RAIL[3],
  ];
  return <RailSection rails={rails} />;
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
  return <RailSection rails={rails} />;
}

// S8 — full coverage (all 3 value rails live) → section-level badge, no per-rail chip.
export function ValueSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const rails: Rail[] = [
    wiredRail(VALUE_RAIL[0], boards?.value_ter, (r) => fundRailRow(r, ter1(r.expense_ratio_pct), false)),
    wiredRail(VALUE_RAIL[1], boards?.value_efficiency, (r) => fundRailRow(r, metricVal(r), true)),
    wiredRail(VALUE_RAIL[2], boards?.value_index, (r) => fundRailRow(r, ter1(r.expense_ratio_pct), false)),
  ];
  return <RailSection rails={rails} />;
}

// S11 — rail 1 retitled to real category-level inflows (fund-level flows don't
// exist by design); rail 2 = aum_growth; rail 3 stays sample.
export function FlowsSection({ boards }: { boards?: LeaderboardBoards } = {}) {
  const rail1: Rail = boards?.category_inflows
    ? {
        title: 'Category Inflow Leaders', q: 'AMFI category-level net flow', icon: FLOW_RAIL[0].icon, color: FLOW_RAIL[0].color, live: true,
        rows: boards.category_inflows.rows.map((r): RailRow => {
          const val = `${r.net_flow_cr >= 0 ? '+' : '−'}${aum(Math.abs(r.net_flow_cr))}`;
          return { name: r.category, logo: initialOf(r.category), color: colorFor(r.category), val, up: r.net_flow_cr >= 0 };
        }),
      }
    : FLOW_RAIL[0];
  const rail2 = liveRail(FLOW_RAIL[1], boards?.aum_growth, (r) => fundRailRow(r, metricVal(r), true));
  const rails: Rail[] = [rail1, rail2, FLOW_RAIL[2]];
  return <RailSection rails={rails} />;
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
export function MarketSection() {
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
      <SoWhat>
        <RichText text="**Market mood is Cautiously Optimistic — typical phase: accumulation.** In similar phases, Flexi Cap & quality Small Cap funds led. This is an educational read of conditions, not a recommendation." />
      </SoWhat>
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
export function ManagersSection() {
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
              {MGR.map((m, i) => (
                <tr key={m.name}>
                  <td className="border-b border-line px-3.5 py-3 text-left font-sans font-extrabold text-ink-muted">{i + 1}</td>
                  <td className="border-b border-line px-3.5 py-3 text-left">
                    <div className="flex items-center gap-2.5">
                      <span className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-full font-sans text-xs font-bold text-white" style={{ background: m.color }}>{m.av}</span>
                      <span className="font-medium text-ink">{m.name}</span>
                    </div>
                  </td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono">{m.exp}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right font-mono">{m.funds}</td>
                  <td className="border-b border-line px-3.5 py-3 text-right"><ScoreWord score={m.score} /></td>
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
        {MGR.map((m, i) => (
          <div key={m.name} className="flex items-center gap-3 border-b border-line py-3 last:border-b-0">
            <span className="w-4 shrink-0 font-sans font-extrabold text-ink-muted">{i + 1}</span>
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full font-sans text-xs font-bold text-white" style={{ background: m.color }}>{m.av}</span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-small font-bold text-ink">{m.name}</div>
              <div className="text-[10.5px] text-ink-muted">{m.exp} · {m.topFund}</div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-[15px]"><ScoreWord score={m.score} /></div>
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
                      <span className="font-medium text-ink">{m.name}</span>
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
              <div className="truncate text-small font-bold text-ink">{m.name}</div>
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
// S15 — TRUSTED ACROSS AGENCIES
// ═══════════════════════════════════════════════════════════════════════════
export function RatingsSection() {
  return (
    <>
      <div className="grid gap-3.5 lg:grid-cols-2">
        {RATINGS.map((r) => {
          const ab = agreeBand(r.agree);
          return (
            <div key={r.name} className="rounded-2xl border border-line bg-surface p-4 shadow-sm sm:p-5">
              <div className="mb-3.5 flex items-center gap-3">
                <Logo letter={r.logo} color={r.color} size={42} radius={11} font={15} />
                <div className="min-w-0">
                  <div className="truncate text-body font-bold text-ink">{r.name}</div>
                  <div className="text-[11.5px] text-ink-muted">Highly rated across all 4 providers</div>
                </div>
                <div className="ml-auto shrink-0 text-right">
                  <div className="font-sans text-base font-extrabold text-emerald">{ab.word}</div>
                  <div className="text-[9.5px] uppercase tracking-[0.04em] text-ink-muted">Agreement</div>
                </div>
              </div>
              <div className="flex flex-col gap-2.5">
                {r.providers.map((p) => (
                  <div key={p.name} className="flex items-center gap-2.5 text-[12.5px]">
                    <span className="flex-1 font-semibold text-ink-secondary">{p.name}</span>
                    {p.kind === 'stars' ? (
                      <span className="text-sm tracking-[1px] text-amber">{p.value}</span>
                    ) : p.kind === 'rank' ? (
                      <span className="font-mono font-extrabold text-royal">{p.value}</span>
                    ) : (
                      <EduPill word={p.value} color={E} />
                    )}
                  </div>
                ))}
              </div>
              <div className="mt-3 h-[7px] overflow-hidden rounded bg-surface-2">
                <div className="h-full rounded bg-emerald" style={{ width: `${ab.fill}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      <SoWhat>
        <RichText text="**When DhanRadar, Morningstar, CRISIL and Value Research all agree, the case is strongest.** A high Agreement reading means independent methodologies reached the same conclusion — the strongest possible validation." />
      </SoWhat>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S16 — AI INSIGHTS
// ═══════════════════════════════════════════════════════════════════════════
export function AiInsightsSection() {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {AI_INSIGHTS.map((t, i) => (
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
export function FilterSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
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
          {FILTER_GROUPS.map(([h, opts]) => (
            <div key={h} className="mb-4">
              <h4 className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-ink-muted">{h}</h4>
              <div className="flex flex-wrap gap-1.5">
                {opts.map((o, i) => (
                  <button
                    key={o}
                    type="button"
                    className={cn(
                      'rounded-lg border px-3 py-1.5 text-[11.5px] font-semibold transition-colors',
                      i === 0 && h === 'Category' ? 'border-royal bg-royal text-white' : 'border-line bg-surface-2 text-ink-secondary',
                    )}
                  >
                    {o}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="sticky bottom-0 flex gap-2.5 border-t border-line bg-surface px-[18px] py-3.5">
          <CTA variant="primary" className="flex-1">Apply</CTA>
          <CTA>Reset</CTA>
        </div>
      </div>
    </>
  );
}

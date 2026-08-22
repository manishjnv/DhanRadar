/**
 * Fund Comparison V3 — section components (S1–S24).
 *
 * Full-parity port of the approved FundComparisonPageV3 desktop + mobile
 * mockups. Each section maps 1:1 to a numbered block in the design. Responsive:
 * fund columns / card grids collapse to one column on small screens; data
 * tables scroll horizontally inside their card. Interactive bits (SIP toggles,
 * risk accordion, FAQ) are client-side React state.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { HeroRing, Accordion, ChipToggle } from '@/components/mf/funddetail/parts';
import {
  FUNDS, EDU_READ, SCOREBOARD, PERF, ROLLING, RANKT, RANK_SERIES,
  RISK_HEAT, ADV_RISK, FIT, HOLD_STATS, HOLDINGS, FLOW, MGRS, AMC, COST, COST_VIS, TAX,
  CHANGES, ALTS, AI_INSIGHTS, FAQ, STICKY, SIPDATA, SIP_AMOUNTS,
  SIP_DURATIONS, fmtCr, toStrength,
} from './sampleData';
import type { CompareFund, Row } from './sampleData';
import {
  SoWhat, RichText, Panel, WinChip, Dot, CompareTable, ScoreboardRows, HeatTable, CTA,
} from './ui';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/apiClient';
import { useWatchlist } from '@/hooks/useWatchlist';
import { Input } from '@/components/ui/Input';
import { useMoodCurrent } from '@/features/mood/api';
import { useMe } from '@/features/auth/api';
import { useFundPortfolioFit, useLatestPortfolio } from '@/features/mf/api';
import { MoodGauge, REGIME_DISPLAY } from '@/components/mood/MoodGauge';
import { relativeTime } from '@/features/mood/relative-time';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import type {
  CompareCompositionFragment, ComparePeopleFragment, CompareFlowFragment,
  CompareEventItem, CompareAmcFragment, CompareAlternative, ComparePairwiseOverlap,
} from '@/features/mf/types';

const STRENGTH_WORD = { strong: 'Strong', good: 'Good', moderate: 'Moderate', soft: 'Soft' } as const;
const ASSESS_TOP = { in_form: 'In Form', on_track: 'On Track', off_track: 'Off Track', out_of_form: 'Out of Form', insufficient_data: '—' } as const;

// ── S1 — Hero fund columns ───────────────────────────────────────────────────
// `funds` override: /mf/compare?funds=<isin> replaces column 1 with the real fund.
const ISIN_RE = /^[A-Z0-9]{12}$/;

type AddFundResult = { isin: string; scheme_name: string; fund_name_short: string | null };

export function HeroSection({ funds = FUNDS }: { funds?: CompareFund[] }) {
  const router = useRouter();
  const { has, toggle } = useWatchlist();
  const [adding, setAdding] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const [results, setResults] = React.useState<AddFundResult[]>([]);
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  // Live cards carry the real ISIN as `key` (page maps frag.isin → key); sample cards use slugs.
  const liveIsins = funds.map((f) => f.key).filter((k) => ISIN_RE.test(k));
  // Picks made from the pure-sample page (0 real ISINs) accumulate here until there
  // are 2+ to compare — a single pick can't build a valid /mf/compare?isins= URL.
  const [pendingIsins, setPendingIsins] = React.useState<string[]>([]);

  function onQueryChange(q: string) {
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (q.trim().length < 2) { setResults([]); return; }
    debounceRef.current = setTimeout(() => {
      api
        .get<AddFundResult[]>(`/mf/search?q=${encodeURIComponent(q)}&limit=8`)
        .then((list) => setResults(Array.isArray(list) ? list.filter((r) => !liveIsins.includes(r.isin) && !pendingIsins.includes(r.isin)) : []))
        .catch(() => setResults([]));
    }, 200);
  }

  function pickFund(isin: string) {
    const combined = [...liveIsins, ...pendingIsins, isin];
    setQuery('');
    setResults([]);
    if (combined.length >= 2) {
      setAdding(false);
      router.push(`/mf/compare?isins=${combined.slice(0, 4).join(',')}`);
    } else {
      // Still short of 2 — keep the picker open and remember this pick.
      setPendingIsins((prev) => [...prev, isin]);
    }
  }

  // Sample cards have no real ISIN behind them — "View"/"Watchlist" send the user
  // to a real search instead of sitting there as a dead disabled button.
  const sampleFallbackHref = (f: CompareFund) => `/mf/explore?q=${encodeURIComponent(f.short || f.name)}`;

  return (
    <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-[repeat(3,1fr)_minmax(140px,160px)]">
      {funds.map((f) => (
        <div
          key={f.key}
          className="relative overflow-hidden rounded-2xl border border-line bg-surface shadow-sm"
        >
          <div className="relative overflow-hidden px-4.5 py-4 text-white" style={{ background: f.topGradient, paddingLeft: 18, paddingRight: 18 }}>
            <div className="relative flex items-center gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white shadow-md">
                <span className="text-lg font-extrabold" style={{ background: f.topGradient, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>{f.logo}</span>
              </div>
              <div className="min-w-0">
                <div className="text-[15.5px] font-bold leading-tight tracking-tight">{f.name}</div>
                <div className="mt-0.5 text-[11px] opacity-80">{f.cat}</div>
              </div>
            </div>
            <div className="relative mt-3.5 flex items-center gap-3">
              <HeroRing color="#fff" band={f.band} size={52} stroke={5} onDark />
              <div>
                <div className="text-[9.5px] font-semibold uppercase tracking-[0.05em] opacity-75">DhanRadar Read</div>
                <div className="text-sm font-bold">{ASSESS_TOP[f.label]}</div>
              </div>
            </div>
          </div>
          <div className="px-4.5 py-3.5" style={{ paddingLeft: 18, paddingRight: 18 }}>
            {([
              { k: 'NAV', v: <>₹{f.nav} <span className="text-[11px] text-emerald">{f.navc}</span></> },
              { k: 'AUM', v: <>₹{f.aum}</> },
              { k: 'Expense', v: f.exp },
              { k: 'Fund age', v: f.age },
              { k: 'Manager', v: <span className="text-[11px]">{f.mgr}</span> },
            ] as { k: string; v: React.ReactNode }[]).map((row, i, a) => (
              <div key={row.k} className={cn('flex justify-between py-2 text-small', i < a.length - 1 && 'border-b border-line')}>
                <span className="text-ink-muted">{row.k}</span>
                <span className="font-mono font-bold text-ink">{row.v}</span>
              </div>
            ))}
            <div className="mt-3 flex flex-wrap gap-1.5">
              {f.badges.map((b) => <WinChip key={b} gold={b.includes('Best Overall') || b.includes('Highest')}>{b}</WinChip>)}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-1.5">
              {ISIN_RE.test(f.key) ? (
                <Link
                  href={`/mf/fund/${f.key}`}
                  className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-xl bg-royal px-3.5 py-2 text-small font-semibold text-white transition-colors hover:bg-royal/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
                >
                  View fund
                </Link>
              ) : (
                <Link
                  href={sampleFallbackHref(f)}
                  title="Sample fund — search real funds like this one"
                  className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-xl bg-royal px-3.5 py-2 text-small font-semibold text-white transition-colors hover:bg-royal/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
                >
                  View fund
                </Link>
              )}
              {ISIN_RE.test(f.key) ? (
                <CTA variant="navy" onClick={() => toggle({ isin: f.key, name: f.name, category: f.cat })}>
                  {has(f.key) ? '✓ Watchlisted' : '＋ Watchlist'}
                </CTA>
              ) : (
                <Link
                  href={sampleFallbackHref(f)}
                  title="Sample fund — search real funds to watchlist"
                  className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-xl bg-navy px-3.5 py-2 text-small font-semibold text-white transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
                >
                  ＋ Watchlist
                </Link>
              )}
            </div>
          </div>
        </div>
      ))}
      {liveIsins.length >= 4 ? null : adding ? (
        <div className="flex min-h-[120px] flex-col gap-2 rounded-2xl border-2 border-dashed border-royal/50 bg-surface p-3">
          {pendingIsins.length > 0 && (
            <div className="text-caption font-semibold text-royal">{pendingIsins.length} fund{pendingIsins.length > 1 ? 's' : ''} selected — add {pendingIsins.length === 1 && liveIsins.length === 0 ? 'one more' : 'another'} to compare</div>
          )}
          <Input
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Search fund name…"
            aria-label="Search a fund to add to this comparison"
          />
          <div className="flex max-h-48 flex-col gap-1 overflow-y-auto">
            {results.map((r) => (
              <button
                key={r.isin}
                type="button"
                onClick={() => pickFund(r.isin)}
                className="rounded-lg px-2.5 py-2 text-left text-small font-medium text-ink transition-colors hover:bg-royal/5 hover:text-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
                title={r.scheme_name}
              >
                {r.fund_name_short ?? r.scheme_name}
              </button>
            ))}
            {query.trim().length >= 2 && results.length === 0 && (
              <span className="px-2.5 py-2 text-caption text-ink-muted">No matching funds.</span>
            )}
          </div>
          <button
            type="button"
            onClick={() => { setAdding(false); setQuery(''); setResults([]); setPendingIsins([]); }}
            className="self-start text-caption font-semibold text-ink-muted hover:text-ink focus-visible:outline-none"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="flex min-h-[120px] flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-line-strong bg-transparent text-small font-semibold text-ink-muted transition-colors hover:border-royal hover:bg-royal/5 hover:text-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
        >
          <span className="text-2xl" aria-hidden="true">＋</span>Add another fund
        </button>
      )}
    </div>
  );
}

// ── S2 — DhanRadar educational read (was Winner card) ────────────────────────
export function EduReadSection({ items, disclosure, notAdvice }: { items?: string[]; disclosure?: string; notAdvice?: string }) {
  if (items) {
    return items.length > 0 ? (
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {items.map((item) => <div key={item} className="rounded-2xl border border-line bg-surface p-4 text-small text-ink-secondary"><RichText text={item} /></div>)}
        </div>
        <DisclosureBundle disclosure={disclosure} notAdvice={notAdvice || 'For education only — not investment advice.'} />
      </div>
    ) : <EmptyState title="Educational read unavailable" description="The comparison read is unavailable for this request." />;
  }
  return (
    <section className="relative overflow-hidden rounded-3xl p-6 text-white shadow-lg sm:p-7" style={{ background: 'linear-gradient(135deg,#052E26,#064E3B 70%)' }}>
      <div className="relative flex flex-wrap items-center gap-5">
        <div className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-white/10 text-3xl" aria-hidden="true">🏆</div>
        <div className="min-w-[240px] flex-1">
          <div className="font-mono text-[11px] font-bold uppercase tracking-[0.1em] text-emerald-200">Strongest on our factor blend</div>
          <div className="mt-1.5 text-[28px] font-extrabold leading-[1.05] tracking-tight sm:text-[28px]">{EDU_READ.fund}</div>
          <div className="mt-3 flex items-center gap-3">
            <span className="h-2 w-[150px] overflow-hidden rounded bg-white/15"><span className="block h-full rounded bg-gradient-to-r from-emerald-400 to-emerald-200" style={{ width: '85%' }} /></span>
            <span className="font-mono text-sm font-bold">High confidence</span>
          </div>
        </div>
      </div>
      <div className="relative mt-5 grid gap-6 border-t border-white/15 pt-4.5 md:grid-cols-2" style={{ paddingTop: 18 }}>
        <div>
          <h5 className="m-0 mb-2.5 font-mono text-[11px] font-bold uppercase tracking-[0.07em] text-emerald-200">✓ Where it leads</h5>
          {EDU_READ.why.map((t) => (
            <div key={t} className="mb-2 flex gap-2 text-[13px] leading-snug text-emerald-50"><span className="shrink-0 font-bold text-emerald-200">✓</span>{t}</div>
          ))}
        </div>
        <div>
          <h5 className="m-0 mb-2.5 font-mono text-[11px] font-bold uppercase tracking-[0.07em] text-red-300">✗ When another may suit you better</h5>
          {EDU_READ.notFor.map((t) => (
            <div key={t} className="mb-2 flex gap-2 text-[13px] leading-snug text-red-100"><span className="shrink-0 font-bold text-red-300">✗</span>{t}</div>
          ))}
        </div>
      </div>
      <div className="relative mt-4.5 grid grid-cols-2 gap-2.5 md:grid-cols-4" style={{ marginTop: 18 }}>
        {EDU_READ.bestAt.map(([label, name]) => (
          <div key={label} className="rounded-xl border border-white/12 bg-white/[0.08] px-3 py-3">
            <div className="text-[10px] font-semibold uppercase tracking-[0.05em] text-emerald-200">{label}</div>
            <div className="mt-1 text-sm font-bold leading-tight">{name}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── S3 — Scoreboard (strength words in sample; real facts when live) ──────────
export function ScoreboardSection({ funds = FUNDS, rows: liveRows }: { funds?: CompareFund[]; rows?: Row[] }) {
  return (
    <Panel>
      <div className="mb-3 flex flex-wrap gap-2">
        {funds.map((f) => (
          <span key={f.key} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-caption font-semibold shadow-sm">
            <span className="grid h-5 w-5 place-items-center rounded-md text-[11px] font-extrabold text-white" style={{ background: f.topGradient }}>{f.logo}</span>{f.short}
          </span>
        ))}
      </div>
      {liveRows
        ? <CompareTable rows={liveRows} firstCol="Metric" funds={funds} />
        : <ScoreboardRows rows={SCOREBOARD} />
      }
    </Panel>
  );
}

// ── S6 — Market mood — shared regime gauge (live via useMoodCurrent) ─────────
export function MoodSection() {
  const { data: mood, isLoading, isError } = useMoodCurrent();

  if (isLoading) {
    return <Panel><Skeleton className="h-28 w-full rounded-xl" /></Panel>;
  }

  if (isError || !mood || mood.data_quality === 'unavailable') {
    return (
      <Panel>
        <EmptyState
          title="Market mood unavailable"
          description="The market mood snapshot could not be loaded. Check back shortly."
        />
      </Panel>
    );
  }

  const regimeLabel = REGIME_DISPLAY[mood.regime] ?? REGIME_DISPLAY.insufficient_data;

  return (
    <Panel>
      <div className="flex flex-wrap items-center gap-6">
        <MoodGauge regime={mood.regime} confidenceBand={mood.confidence_band} className="shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-bold text-ink">{regimeLabel}</div>
          <div className="mt-1.5 text-small leading-relaxed text-ink-muted">
            All compared funds operate in the same market environment. The current regime is a
            factual reading — past behaviour in a given regime does not predict future results.
          </div>
          <Link
            href="/mood"
            className="mt-2 inline-flex items-center gap-1 text-caption font-semibold text-royal hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
          >
            Full market mood →
          </Link>
        </div>
      </div>
    </Panel>
  );
}

// ── S7 — Performance center ──────────────────────────────────────────────────
export function PerformanceSection({ rows = PERF, funds, live = false, catRows, benchmarkRows }: { rows?: Row[]; funds?: CompareFund[]; live?: boolean; catRows?: Row[]; benchmarkRows?: Row[] }) {
  const displayRows = benchmarkRows ? [...rows, ...catRows ?? [], ...benchmarkRows] : catRows ? [...rows, ...catRows] : rows;
  return (
    <Panel>
      <CompareTable rows={displayRows} firstCol="Period" showCategory={!live} funds={funds} />
      <SoWhat>
        <RichText
          text={
            live
              ? 'Period returns are factual point-in-time figures — read them alongside risk and cost, never in isolation. Category p50 rows show the median fund in each period. Past performance does not indicate future returns.'
              : '**So what:** Quant leads on raw 3Y/5Y returns, but Bandhan is close behind with a far smoother ride. Over 1Y all three beat the category — small-caps have been in form.'
          }
        />
      </SoWhat>
    </Panel>
  );
}

// ── S8 — SIP comparison ──────────────────────────────────────────────────────

/** One fund's SIP entry from the compare bundle (two fixed durations). */
export interface SipEntry {
  fund: CompareFund;
  sip_5y: { amount: number; total_invested: number | null; final_value: number | null; xirr_pct: number | null } | null;
  sip_10y: { amount: number; total_invested: number | null; final_value: number | null; xirr_pct: number | null } | null;
}

function fmtLakh(v: number | null): string {
  if (v == null) return '—';
  return `₹${(v / 100000).toFixed(2)} L`;
}

export function SipSection({ live = false, entries }: { live?: boolean; entries?: SipEntry[] }) {
  const [amt, setAmt] = React.useState('10000');
  const [dur, setDur] = React.useState('5');

  if (live && entries && entries.length > 0) {
    const amount = entries[0].sip_5y?.amount ?? entries[0].sip_10y?.amount ?? 10000;
    return (
      <Panel>
        <div className="mb-3 text-small text-ink-muted">
          Historical SIP illustration — ₹{amount.toLocaleString('en-IN')}/month based on actual past NAVs. Not a projection.
        </div>
        <div className="grid gap-3">
          {entries.map(({ fund, sip_5y, sip_10y }) => (
            <div key={fund.key} className="flex flex-wrap items-center gap-4 rounded-2xl border border-line p-4">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl font-extrabold text-white" style={{ background: fund.topGradient }}>{fund.logo}</div>
              <div className="min-w-[120px] flex-1">
                <div className="text-small font-bold text-ink">{fund.short}</div>
                <div className="text-caption text-ink-muted">₹{amount.toLocaleString('en-IN')}/month SIP</div>
              </div>
              <div className="ml-auto grid grid-cols-2 gap-6 sm:gap-8">
                {([['5 years', sip_5y], ['10 years', sip_10y]] as [string, SipEntry['sip_5y']][]).map(([label, s]) => (
                  <div key={label} className="text-right">
                    <div className="font-mono text-[15px] font-bold text-ink">{fmtLakh(s?.final_value ?? null)}</div>
                    <div className="mt-0.5 text-[10px] font-semibold uppercase text-ink-muted">{label}</div>
                    <div className="mt-0.5 font-mono text-[11px] text-emerald">{s?.xirr_pct != null ? `${s.xirr_pct.toFixed(1)}% XIRR` : '—'}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <SoWhat>
          <RichText text="Historical SIP figures show what a fixed monthly contribution grew to over the stated period, based on actual past NAVs. Past outcomes do not predict future results. Illustrative only — not advice." />
        </SoWhat>
      </Panel>
    );
  }

  // Sample / preview fallback (interactive amount + duration toggles)
  const [invested, vals, xirrs] = SIPDATA[`${amt}_${dur}`];
  return (
    <Panel>
      <div className="mb-4 flex flex-wrap gap-2">
        <ChipToggle options={SIP_AMOUNTS} active={amt} onChange={setAmt} />
        <ChipToggle options={SIP_DURATIONS} active={dur} onChange={setDur} />
      </div>
      <div className="grid gap-3">
        {FUNDS.map((f, i) => {
          const cur = vals[i] * 1000;
          const profit = cur - invested;
          return (
            <div key={f.key} className="flex flex-wrap items-center gap-4 rounded-2xl border border-line p-4">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl font-extrabold text-white" style={{ background: f.topGradient }}>{f.logo}</div>
              <div>
                <div className="text-small font-bold text-ink">{f.short}</div>
                <div className="text-caption text-ink-muted">Invested ₹{invested.toLocaleString('en-IN')} · {dur}Y</div>
              </div>
              <div className="ml-auto grid grid-cols-3 gap-5 sm:gap-6">
                {([[fmtCr(vals[i]), 'Value', 'text-ink'], [`+${fmtCr(profit / 1000)}`, 'Profit', 'text-emerald'], [`${xirrs[i]}%`, 'XIRR', 'text-emerald']] as [string, string, string][]).map(([v, l, c]) => (
                  <div key={l} className="text-right">
                    <div className={cn('font-mono text-[15px] font-bold', c)}>{v}</div>
                    <div className="mt-0.5 text-[10px] font-semibold uppercase text-ink-muted">{l}</div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <SoWhat>
        <RichText text={`Historical SIP figures for ₹${(+amt).toLocaleString('en-IN')}/month over ${dur} years, based on past NAVs. Not a projection. Illustrative only — not advice.`} />
      </SoWhat>
    </Panel>
  );
}

// ── S9 — Rolling returns ─────────────────────────────────────────────────────
export function RollingSection({ rows = ROLLING, live = false }: { rows?: Row[]; live?: boolean }) {
  return (
    <Panel>
      <CompareTable rows={rows} firstCol="Rolling window" />
      <SoWhat>
        <RichText text={live
          ? "Rolling figures show average past return and the fraction of overlapping windows that ended positive. A higher percentage of positive windows reflects steadier past outcomes — not a forecast of future consistency."
          : "**So what:** Rolling returns reward consistency. **Bandhan** beat its category in **78%** of rolling 3-yr windows — the highest hit-rate of the three."
        } />
      </SoWhat>
    </Panel>
  );
}

// ── S10 — Ranking + multi-line rank chart ────────────────────────────────────
function MultiRankChart() {
  const W = 800, H = 150, maxR = 10;
  return (
    <div className="mt-4 rounded-2xl border border-line p-4" style={{ background: 'linear-gradient(180deg,#F8FAFC,#fff)' }}>
      <div className="mb-2 text-caption font-semibold text-ink-secondary">Historical category rank (lower = better)</div>
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="block">
        {FUNDS.map((f) => {
          const d = RANK_SERIES[f.key];
          const pts = d.map((v, i) => [(i / (d.length - 1)) * W, ((v - 1) / (maxR - 1)) * (H - 16) + 8]);
          const path = 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
          return (
            <g key={f.key}>
              <path d={path} fill="none" stroke={f.color} strokeWidth="2.2" />
              {pts.map(([x, y], i) => <circle key={i} cx={x.toFixed(1)} cy={y.toFixed(1)} r="2.5" fill={f.color} />)}
            </g>
          );
        })}
        <text x="4" y="13" fontFamily="var(--font-mono,monospace)" fontSize="10" fill="#94A3B8">#1</text>
        <text x="4" y={H - 5} fontFamily="var(--font-mono,monospace)" fontSize="10" fill="#94A3B8">#10</text>
      </svg>
      <div className="mt-2.5 flex flex-wrap gap-4 text-caption text-ink-muted">
        {FUNDS.map((f) => <span key={f.key} className="inline-flex items-center gap-1.5"><span className="h-[3px] w-2.5 rounded-sm" style={{ background: f.color }} />{f.short}</span>)}
      </div>
    </div>
  );
}

export function RankingSection({ rows = RANKT, funds, live = false }: { rows?: Row[]; funds?: CompareFund[]; live?: boolean }) {
  return (
    <Panel>
      <CompareTable rows={rows} firstCol="Metric" funds={funds} />
      {live ? (
        <div className="mt-4 rounded-2xl border border-line bg-surface p-4 text-center text-caption text-ink-muted">
          Rank trend chart appears here as rank history builds.
        </div>
      ) : (
        <MultiRankChart />
      )}
      <SoWhat>
        <RichText
          text={
            live
              ? '**So what:** Category rank is a factual position within the SEBI category — a snapshot that moves over time, not a projection.'
              : '**So what:** **Bandhan** has the most consistent ranking (always top 4). **Quant** is the best improver. **Nippon** is the best long-term performer.'
          }
        />
      </SoWhat>
    </Panel>
  );
}

// ── S11 — Risk center + advanced accordion ───────────────────────────────────
export function RiskSection({ liveRows }: { liveRows?: Row[] }) {
  return (
    <Panel>
      <div className="mb-3 text-small text-ink-muted">Traffic-light read — green is lower risk / better protection:</div>
      <HeatTable rows={RISK_HEAT} />
      <Accordion title={<span>▸ Standard risk ratios <span className="text-caption font-normal text-ink-faint">(Sharpe, Sortino, std dev, max drawdown)</span></span>}>
        <CompareTable rows={liveRows ?? ADV_RISK} firstCol="Metric" />
      </Accordion>
      <SoWhat>
        <RichText text={liveRows
          ? "Sharpe and Sortino ratios measure return per unit of total and downside risk respectively — higher values indicate more return for the risk taken historically. Max drawdown shows the worst peak-to-trough fall in the period. Standard published ratios only — not the DhanRadar composite."
          : "**So what:** **Bandhan** is the lowest-risk of the three — best downside capture and drawdown. **Quant** takes the most risk for the most reward. Match the choice to your own comfort with swings."
        } />
      </SoWhat>
    </Panel>
  );
}

// ── S12 — Portfolio fit ──────────────────────────────────────────────────────
// Per-fund child: useFundPortfolioFit is always called unconditionally inside.
function FundFitCard({ portfolioId, isin, fund }: { portfolioId: string; isin: string; fund: CompareFund }) {
  const { data: envelope, isLoading, isError } = useFundPortfolioFit(portfolioId, isin);
  const fit = envelope?.data ?? null;

  return (
    <div className="rounded-2xl border border-line p-4">
      <div className="mb-3 flex items-center gap-2.5">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl font-extrabold text-white" style={{ background: fund.topGradient }}>{fund.logo}</div>
        <div className="text-sm font-bold text-ink">{fund.short}</div>
      </div>
      {isLoading ? (
        <Skeleton className="h-20 w-full rounded-xl" />
      ) : isError || !fit ? (
        <EmptyState
          title="Portfolio fit unavailable"
          description="Upload your CAS statement to see how this fund relates to your portfolio."
          className="py-4"
        />
      ) : (
        <div className="space-y-1">
          {fit.category_allocation_pct != null && (
            <div className="flex justify-between py-1 text-caption border-b border-line">
              <span className="text-ink-muted">Category in your portfolio</span>
              <span className="font-mono font-bold text-ink">{fit.category_allocation_pct.toFixed(1)}%</span>
            </div>
          )}
          {fit.fund_count_in_category != null && (
            <div className="flex justify-between py-1 text-caption border-b border-line">
              <span className="text-ink-muted">Funds in category you hold</span>
              <span className="font-mono font-bold text-ink">{fit.fund_count_in_category}</span>
            </div>
          )}
          {fit.overlap.length > 0 && (
            <div className="mt-2">
              <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.05em] text-ink-muted">Holdings overlap with funds you hold</div>
              {fit.overlap.slice(0, 3).map((entry) => (
                <div key={entry.holding_name} className="flex justify-between py-1 text-caption">
                  <span className="truncate text-ink-secondary">{entry.holding_name}</span>
                  <span className="ml-2 shrink-0 font-mono font-bold text-ink">{entry.overlap_pct.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          )}
          <div className="mt-2 rounded-lg bg-surface-2 p-2.5 text-[11px] leading-snug text-ink-muted">{fit.observation}</div>
        </div>
      )}
    </div>
  );
}

export function FitSection({ isins, funds }: { isins?: string[]; funds?: CompareFund[] }) {
  // Always called unconditionally; FundFitCard also calls its hook unconditionally.
  const { data: me, isLoading: meLoading, isError: meIsError } = useMe();
  const { data: latestPortfolio } = useLatestPortfolio();
  const portfolioId = latestPortfolio?.portfolio_id ?? '';
  const isAnonymous = !meLoading && (meIsError || !me);
  const live = !!isins && isins.length >= 2 && !!funds;

  if (!live) {
    return (
      <div className="grid grid-cols-1 gap-3.5 lg:grid-cols-3">
        {FIT.map((c) => {
          const f = FUNDS.find((x) => x.key === c.key)!;
          return (
            <div key={c.key} className="rounded-2xl border border-line p-4.5" style={{ padding: 18 }}>
              <div className="text-sm font-bold text-ink">{f.short}</div>
              <div className="mt-3">
                {c.rows.map(([l, v], i, a) => (
                  <div key={l} className={cn('flex justify-between py-1.5 text-caption', i < a.length - 1 && 'border-b border-line')}>
                    <span className="text-ink-muted">{l}</span><span className="font-mono font-bold text-ink">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  if (meLoading) {
    return <Panel><Skeleton className="h-48 w-full rounded-xl" /></Panel>;
  }

  if (isAnonymous) {
    return (
      <Panel>
        <EmptyState
          title="Sign in to see portfolio fit"
          description="Compare these funds with your own holdings after uploading your CAS statement."
        />
      </Panel>
    );
  }

  if (!portfolioId) {
    return (
      <Panel>
        <EmptyState
          title="No portfolio on file"
          description="Upload your CAS statement to compare these funds against your own portfolio."
        />
      </Panel>
    );
  }

  return (
    <div className={cn('grid grid-cols-1 gap-3.5', funds.length === 2 ? 'lg:grid-cols-2' : 'lg:grid-cols-3')}>
      {funds.map((fund, i) => (
        <FundFitCard key={fund.key} portfolioId={portfolioId} isin={isins[i]!} fund={fund} />
      ))}
    </div>
  );
}

// ── S13 — Holdings comparison ────────────────────────────────────────────────
export function HoldingsSection({
  compositions,
  pairwiseOverlap,
  funds = FUNDS,
  isins,
}: {
  compositions?: Record<string, CompareCompositionFragment | null>;
  pairwiseOverlap?: ComparePairwiseOverlap[];
  funds?: CompareFund[];
  isins?: string[];
}) {
  if (!compositions || !pairwiseOverlap) {
    return (
      <Panel>
        <div className="mb-4 flex flex-wrap items-center gap-3.5">
          <div className="flex items-center gap-2.5">
            <div className="text-3xl font-extrabold text-amber">31%</div>
            <div className="text-caption leading-tight text-ink-muted">Portfolio similarity<br />between all 3 funds</div>
          </div>
          <div className="min-w-[200px] flex-1 text-small leading-relaxed text-ink-secondary">They share <b className="text-ink">18 common stocks</b> but weight them very differently — so holding two of these adds less diversification than you&apos;d think.</div>
        </div>
        <CompareTable rows={HOLD_STATS} firstCol="Metric" />
        <div className="mt-4 grid grid-cols-1 gap-3.5 sm:grid-cols-3">
          {FUNDS.map((f) => (
            <div key={f.key}>
              <h4 className="m-0 mb-2.5 flex items-center gap-1.5 text-caption font-bold text-ink"><Dot color={f.color} size={9} />{f.short} · top 5</h4>
              {HOLDINGS[f.key].map(([n, w, shared]) => (
                <div key={n} className="flex items-center gap-2.5 border-b border-line py-2 last:border-b-0">
                  <div className="flex-1 text-caption font-semibold text-ink">{n} {shared && <span className="rounded bg-amber/15 px-1.5 py-px font-mono text-[8.5px] font-bold text-amber">SHARED</span>}</div>
                  <div className="font-mono text-caption font-bold text-ink">{w}%</div>
                </div>
              ))}
            </div>
          ))}
        </div>
        <SoWhat><RichText text="Holdings concentration and overlap vary by fund. Lower top-10 concentration typically indicates broader diversification. Overlap computed from disclosed holdings only." /></SoWhat>
      </Panel>
    );
  }

  const isinToFund: Record<string, CompareFund> = {};
  (isins ?? []).forEach((isin, i) => { if (funds[i]) isinToFund[isin] = funds[i]; });
  const fundShort = (isin: string) => isinToFund[isin]?.short ?? isin.slice(-6);

  return (
    <div className="space-y-4">
      {pairwiseOverlap.length > 0 && (
        <Panel>
          <h4 className="m-0 mb-3 text-small font-bold text-ink">Holdings Overlap (disclosed top-10)</h4>
          <div className={cn('grid grid-cols-1 gap-3', pairwiseOverlap.length === 1 ? 'sm:grid-cols-1' : 'sm:grid-cols-2 lg:grid-cols-3')}>
            {pairwiseOverlap.map((pair) => {
              const pairKey = `${pair.isin_a}-${pair.isin_b}`;
              if (pair.no_data) {
                return (
                  <div key={pairKey} className="rounded-xl border border-line p-4">
                    <div className="mb-2 text-[11px] font-semibold text-ink-muted">{fundShort(pair.isin_a)} vs {fundShort(pair.isin_b)}</div>
                    <EmptyState
                      title="Overlap data unavailable"
                      description="Constituent data absent for one or both funds — overlap cannot be computed."
                      className="py-3"
                    />
                  </div>
                );
              }
              return (
                <div key={pairKey} className="rounded-xl border border-line p-4">
                  <div className="mb-1 text-[11px] font-semibold text-ink-muted">{fundShort(pair.isin_a)} vs {fundShort(pair.isin_b)}</div>
                  <div className="text-2xl font-extrabold text-ink">{pair.overlap_pct.toFixed(1)}%</div>
                  <div className="text-[11px] text-ink-muted">disclosed-holdings overlap</div>
                  {pair.common_holdings.length > 0 && (
                    <div className="mt-2.5 space-y-1">
                      {pair.common_holdings.slice(0, 5).map((h) => (
                        <div key={h.name} className="flex items-center justify-between text-[11px]">
                          <span className="truncate text-ink-secondary">{h.name}</span>
                          <span className="ml-2 shrink-0 font-mono text-ink-faint">
                            {h.weight_a != null ? `${h.weight_a.toFixed(1)}%` : '—'} / {h.weight_b != null ? `${h.weight_b.toFixed(1)}%` : '—'}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div className="mt-2 text-[10.5px] text-ink-muted">
            Overlap uses top-10 disclosed holdings only (major-AMC coverage). Figures may understate total overlap.
          </div>
        </Panel>
      )}
      <Panel>
        <h4 className="m-0 mb-3 text-small font-bold text-ink">Top Holdings by Fund</h4>
        <div className={cn('grid grid-cols-1 gap-3.5', funds.length === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-3')}>
          {funds.map((f, i) => {
            const isin = isins?.[i];
            const frag = isin ? (compositions[isin] ?? null) : null;
            if (!frag || frag.no_data) {
              return (
                <div key={f.key}>
                  <h4 className="m-0 mb-2.5 flex items-center gap-1.5 text-caption font-bold text-ink"><Dot color={f.color} size={9} />{f.short}</h4>
                  <EmptyState title="Holdings unavailable" className="py-4" />
                </div>
              );
            }
            return (
              <div key={f.key}>
                <h4 className="m-0 mb-2.5 flex items-center gap-1.5 text-caption font-bold text-ink"><Dot color={f.color} size={9} />{f.short} · top {Math.min(frag.data.holdings.length, 5)}</h4>
                {frag.data.holdings.slice(0, 5).map((h) => (
                  <div key={h.name} className="flex items-center gap-2.5 border-b border-line py-2 last:border-b-0">
                    <div className="flex-1 text-caption font-semibold text-ink">{h.name}</div>
                    <div className="font-mono text-caption font-bold text-ink">{h.weight_pct != null ? `${h.weight_pct.toFixed(1)}%` : '—'}</div>
                  </div>
                ))}
                {frag.data.as_of_month && (
                  <div className="mt-1 text-[10px] text-ink-faint">As of {frag.data.as_of_month}</div>
                )}
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

// ── S14 — Fund flow (category-level only — compliance §14.3) ─────────────────
export function FlowSection({
  flows,
  funds = FUNDS,
  isins,
}: {
  flows?: Record<string, CompareFlowFragment | null>;
  funds?: CompareFund[];
  isins?: string[];
}) {
  if (!flows) {
    return (
      <Panel>
        <CompareTable rows={FLOW} firstCol="Metric" />
        <SoWhat><RichText text="Category-level AMFI fund flow data — shows net flows for funds in the same SEBI category. Not specific to any individual fund." /></SoWhat>
      </Panel>
    );
  }

  return (
    <div>
      <div className={cn('grid grid-cols-1 gap-3.5', funds.length === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-3')}>
        {funds.map((f, i) => {
          const isin = isins?.[i];
          const frag = isin ? (flows[isin] ?? null) : null;

          if (!frag || frag.source_blocked) {
            const cat = frag?.source_blocked ? frag.scheme_category : null;
            return (
              <Panel key={f.key}>
                <h4 className="m-0 mb-3 flex items-center gap-2 text-[13.5px] font-bold text-ink"><Dot color={f.color} />{f.short}</h4>
                <EmptyState
                  title="Flow data unavailable"
                  description={cat
                    ? `Category flow data for "${cat}" is not yet available.`
                    : 'Category flow data is not yet available for this fund.'}
                  className="py-4"
                />
              </Panel>
            );
          }

          const latest = frag.points.slice(-3);
          return (
            <Panel key={f.key}>
              <h4 className="m-0 mb-1 flex items-center gap-2 text-[13.5px] font-bold text-ink"><Dot color={f.color} />{f.short}</h4>
              {frag.scheme_category && (
                <div className="mb-3 text-[11px] text-ink-muted">Funds in category: {frag.scheme_category}</div>
              )}
              <div className="space-y-1">
                {latest.map((pt) => (
                  <div key={pt.period_month} className="flex justify-between text-caption">
                    <span className="text-ink-muted">{pt.period_month}</span>
                    <span className={cn('font-mono font-bold', pt.net_flow_cr != null && pt.net_flow_cr >= 0 ? 'text-emerald' : 'text-[#E5484D]')}>
                      {pt.net_flow_cr != null
                        ? `${pt.net_flow_cr >= 0 ? '+' : ''}${pt.net_flow_cr.toLocaleString('en-IN', { maximumFractionDigits: 0 })} Cr`
                        : '—'}
                    </span>
                  </div>
                ))}
              </div>
              {frag.as_of_month && (
                <div className="mt-1.5 text-[10px] text-ink-faint">As of {frag.as_of_month}</div>
              )}
            </Panel>
          );
        })}
      </div>
      <p className="mt-2 text-[11px] text-ink-muted">
        Category-level AMFI net flows — figures reflect all funds in each SEBI category, not this specific fund.
      </p>
    </div>
  );
}

// ── S15 — Managers ────────────────────────────────────────────────────────────
export function ManagerSection({
  people,
  funds = FUNDS,
  isins,
}: {
  people?: Record<string, ComparePeopleFragment | null>;
  funds?: CompareFund[];
  isins?: string[];
}) {
  if (!people) {
    return (
      <div className="grid grid-cols-1 gap-3.5 lg:grid-cols-3">
        {MGRS.map((m) => {
          const f = FUNDS.find((x) => x.key === m.key)!;
          const s = toStrength(m.strengthScore);
          return (
            <div key={m.key} className="rounded-2xl border border-line p-4">
              <div className="flex items-center gap-2.5">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-base font-extrabold text-white" style={{ background: f.topGradient }}>{m.init}</div>
                <div>
                  <div className="text-sm font-bold text-ink">{m.name}</div>
                  <div className="text-[11px] text-ink-muted">{f.short}</div>
                </div>
              </div>
              <div className="mt-3">
                {[...m.rows, ['Manager track', STRENGTH_WORD[s]] as [string, string]].map(([l, v], i, a) => (
                  <div key={l} className={cn('flex justify-between py-1.5 text-caption', i < a.length - 1 && 'border-b border-line')}>
                    <span className="text-ink-muted">{l}</span><span className="font-mono font-bold text-ink">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className={cn('grid grid-cols-1 gap-3.5', funds.length === 2 ? 'lg:grid-cols-2' : 'lg:grid-cols-3')}>
      {funds.map((f, i) => {
        const isin = isins?.[i];
        const frag = isin ? (people[isin] ?? null) : null;

        if (!frag || frag.no_data) {
          return (
            <div key={f.key} className="rounded-2xl border border-line p-4">
              <div className="mb-2 flex items-center gap-2.5">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-base font-extrabold text-white" style={{ background: f.topGradient }}>{f.logo}</div>
                <div className="text-sm font-bold text-ink">{f.short}</div>
              </div>
              <EmptyState
                title="Manager data unavailable"
                description="Manager information is not available for this fund (coverage ~13% of funds)."
                className="py-4"
              />
            </div>
          );
        }

        return (
          <div key={f.key} className="rounded-2xl border border-line p-4">
            <div className="mb-3 flex items-center gap-2.5">
              <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-base font-extrabold text-white" style={{ background: f.topGradient }}>{f.logo}</div>
              <div className="text-sm font-bold text-ink">{f.short}</div>
            </div>
            {frag.managers.map((mgr) => (
              <div key={mgr.name} className="mb-3 last:mb-0">
                <div className="text-small font-bold text-ink">{mgr.name}</div>
                <div className="mt-1.5 space-y-1">
                  <div className="flex justify-between text-caption">
                    <span className="text-ink-muted">Tenure</span>
                    <span className="font-mono font-bold text-ink">{mgr.tenure_years.toFixed(1)} yrs</span>
                  </div>
                  {mgr.tenure_return_pct != null && (
                    <div className="flex justify-between text-caption">
                      <span className="text-ink-muted">Return since joining</span>
                      <span className="font-mono font-bold text-ink">{mgr.tenure_return_pct.toFixed(1)}%</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div className="mt-2 flex justify-between border-t border-line pt-2 text-caption">
              <span className="text-ink-muted">Manager changes (5Y)</span>
              <span className="font-mono font-bold text-ink">{frag.manager_changes_5y}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── S16 — AMC comparison ──────────────────────────────────────────────────────
export function AmcSection({
  amcData,
  funds = FUNDS,
  isins,
}: {
  amcData?: Record<string, CompareAmcFragment | null>;
  funds?: CompareFund[];
  isins?: string[];
}) {
  if (!amcData) {
    return (
      <Panel>
        <CompareTable rows={AMC} firstCol="Metric" />
        <SoWhat><RichText text="AMC facts from AMFI reporting — scheme count and category breadth are factual aggregates. AUM shown is the AMC-level total across all their schemes, not this fund's own AUM." /></SoWhat>
      </Panel>
    );
  }

  const liveRows: Row[] = [
    {
      label: 'Schemes managed',
      vals: (isins ?? []).map((isin) => {
        const amc = amcData[isin];
        return amc ? String(amc.scheme_count) : null;
      }),
    },
    {
      label: 'Categories covered',
      vals: (isins ?? []).map((isin) => {
        const amc = amcData[isin];
        return amc ? String(amc.category_count) : null;
      }),
    },
    {
      label: 'AMC-level AUM',
      vals: (isins ?? []).map((isin) => {
        const amc = amcData[isin];
        if (!amc || amc.amc_level_aum_crore == null) return null;
        return `₹${(amc.amc_level_aum_crore / 100000).toFixed(1)}L Cr`;
      }),
    },
  ];

  const amcNames = (isins ?? []).map((isin) => amcData[isin]?.amc_name ?? null);

  return (
    <Panel>
      {amcNames.some(Boolean) && (
        <div className="mb-3 flex flex-wrap gap-2">
          {funds.map((f, i) => amcNames[i] ? (
            <span key={f.key} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-caption font-semibold shadow-sm">
              <Dot color={f.color} size={7} />{amcNames[i]}
            </span>
          ) : null)}
        </div>
      )}
      <CompareTable rows={liveRows} firstCol="AMC metric" funds={funds} />
      <div className="mt-2 text-[10.5px] text-ink-muted">
        AMC-level AUM is the total across all schemes managed by the AMC — not this fund&apos;s own AUM.
      </div>
    </Panel>
  );
}

// ── S17 — Cost comparison + cost-vis bars ────────────────────────────────────
export function CostSection({ rows = COST, vis = COST_VIS, funds, live = false }: { rows?: Row[]; vis?: [string, number, string][]; funds?: CompareFund[]; live?: boolean }) {
  const cmax = vis.length ? Math.max(...vis.map(([, v]) => v)) : 0;
  return (
    <Panel>
      <CompareTable rows={rows} firstCol="Metric" funds={funds} />
      {vis.length > 0 && (
        <>
          <div className="mt-4.5 mb-1.5 text-small font-semibold text-ink-secondary" style={{ marginTop: 18 }}>💸 Hidden cost on ₹10 L — total fees paid</div>
          <div className="mt-3.5">
            {vis.map(([n, v, c]) => (
              <div key={n} className="mb-3 flex items-center gap-3">
                <span className="flex w-[110px] shrink-0 items-center gap-1.5 text-small font-semibold sm:w-[120px]"><Dot color={c} size={9} />{n}</span>
                <div className="relative h-[30px] flex-1 overflow-hidden rounded-lg bg-surface-2">
                  <span className="flex h-full items-center justify-end rounded-lg pr-2.5 font-mono text-caption font-bold text-white" style={{ width: `${(v / cmax) * 100}%`, background: c }}>₹{v.toFixed(1)} L</span>
                </div>
              </div>
            ))}
            <div className="mt-1 text-caption text-ink-muted">Total fees on a ₹10 L lump-sum held 15 years (at similar returns).</div>
          </div>
        </>
      )}
      <SoWhat>
        <RichText
          text={
            live
              ? '**So what:** A lower expense ratio compounds in your favour over long holding periods — cost is one of the few things about a fund known in advance.'
              : "**So what:** Over 15 years, Bandhan's lower expense ratio works out to roughly **₹2.1 lakh** less in fees than Quant on a ₹10 L investment — money that stays compounding for you."
          }
        />
      </SoWhat>
    </Panel>
  );
}

// ── S18 — Tax ────────────────────────────────────────────────────────────────
function taxRuleFromCategory(cat: string): { ltcg: string; stcg: string; holding: string } {
  const c = cat.toLowerCase();
  const isDebt = c.includes('debt') || c.includes('liquid') || c.includes('overnight') ||
    c.includes('gilt') || c.includes('money market') || c.includes('banking and psu') ||
    (c.includes('hybrid') && (c.includes('conservative') || c.includes('arbitrage')));
  if (isDebt) {
    return { ltcg: 'Marginal rate (no LTCG window)', stcg: 'Marginal rate', holding: 'No LTCG window' };
  }
  return { ltcg: '12.5% (gains > ₹1.25 L/yr)', stcg: '20%', holding: '1 year' };
}

export function TaxSection({ categories }: { categories?: string[] }) {
  if (categories && categories.length > 0) {
    const rules = categories.map((c) => taxRuleFromCategory(c));
    const liveRows: Row[] = [
      { label: 'LTCG rate', vals: rules.map((r) => r.ltcg) },
      { label: 'STCG rate', vals: rules.map((r) => r.stcg) },
      { label: 'LTCG holding period', vals: rules.map((r) => r.holding) },
    ];
    const allEquity = rules.every((r) => r.ltcg.startsWith('12.5'));
    return (
      <Panel>
        <CompareTable rows={liveRows} firstCol="Tax (on ₹2 L gain)" />
        <SoWhat>
          <RichText text={allEquity
            ? "All compared funds fall under the equity tax category — LTCG at 12.5% applies after 1 year, with ₹1.25 lakh exemption annually. Verify exit load schedules in the scheme documents."
            : "Tax treatment varies by category — equity-oriented funds qualify for LTCG after 1 year; debt-oriented funds are taxed at your marginal rate regardless of holding period. Verify with current applicable rules."
          } />
        </SoWhat>
      </Panel>
    );
  }
  return (
    <Panel>
      <CompareTable rows={TAX} firstCol="On ₹2L gain (>1yr)" />
      <SoWhat><RichText text="All three are equity funds — LTCG applies after 1 year, with ₹1.25 lakh annual exemption. Verify exit load schedules in each scheme’s SID." /></SoWhat>
    </Panel>
  );
}


// ── S20 — What changed ───────────────────────────────────────────────────────
const SEV_COLOR: Record<string, string> = { notable: '#F59E0B', info: '#1E5EFF' };
export function ChangesSection({
  events,
  funds = FUNDS,
  isins,
}: {
  events?: Record<string, CompareEventItem[] | null>;
  funds?: CompareFund[];
  isins?: string[];
}) {
  if (!events) {
    return (
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        {FUNDS.map((f) => (
          <Panel key={f.key}>
            <h4 className="m-0 mb-3.5 flex items-center gap-2 text-[13.5px] font-bold text-ink"><Dot color={f.color} />{f.short}</h4>
            <div className="relative pl-5">
              <span className="absolute bottom-1.5 left-[5px] top-1.5 w-0.5 bg-line" aria-hidden="true" />
              {CHANGES[f.key].map(([, txt, time], i) => (
                <div key={i} className="relative pb-3 last:pb-0">
                  <span className="absolute -left-5 top-[3px] h-[11px] w-[11px] rounded-full border-2 border-surface bg-royal" aria-hidden="true" />
                  <div className="text-small leading-snug text-ink-secondary">{txt}</div>
                  <div className="mt-0.5 font-mono text-[10.5px] text-ink-faint">{time}</div>
                </div>
              ))}
            </div>
          </Panel>
        ))}
      </div>
    );
  }

  return (
    <div className={cn('grid grid-cols-1 gap-3.5', funds.length === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-3')}>
      {funds.map((f, i) => {
        const isin = isins?.[i];
        const fundEvents = (isin ? (events[isin] ?? []) : []).slice(0, 5);
        return (
          <Panel key={f.key}>
            <h4 className="m-0 mb-3.5 flex items-center gap-2 text-[13.5px] font-bold text-ink"><Dot color={f.color} />{f.short}</h4>
            {fundEvents.length === 0 ? (
              <EmptyState title="No recent changes" className="py-4" />
            ) : (
              <div className="relative pl-5">
                <span className="absolute bottom-1.5 left-[5px] top-1.5 w-0.5 bg-line" aria-hidden="true" />
                {fundEvents.map((ev, idx) => (
                  <div key={idx} className="relative pb-3 last:pb-0">
                    <span
                      className="absolute -left-5 top-[3px] h-[11px] w-[11px] rounded-full border-2 border-surface"
                      style={{ background: SEV_COLOR[ev.severity] ?? SEV_COLOR.info }}
                      aria-hidden="true"
                    />
                    <div className="text-small leading-snug text-ink-secondary">{ev.summary}</div>
                    <div className="mt-0.5 font-mono text-[10.5px] text-ink-faint">{relativeTime(ev.as_of)}</div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        );
      })}
    </div>
  );
}

// ── S21 — Alternatives (strength word, no score number) ──────────────────────
export function AltsSection({ alternatives }: { alternatives?: CompareAlternative[] }) {
  if (alternatives && alternatives.length > 0) {
    return (
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
        {alternatives.map((a) => (
          <div key={a.isin} className="rounded-2xl border border-line p-4">
            <div className="text-[13.5px] font-bold leading-tight text-ink">{a.fund_name_short ?? a.scheme_name}</div>
            <div className="mt-0.5 text-[11px] text-ink-muted">{a.amc_name ?? '—'}</div>
            <div className="mt-0.5 text-[10px] text-ink-faint">{a.sebi_category ?? '—'}</div>
            <div className="my-3 grid grid-cols-3 gap-2">
              {([
                [a.return_3y_pct != null ? `${a.return_3y_pct.toFixed(1)}%` : '—', '3Y'],
                [a.return_1y_pct != null ? `${a.return_1y_pct.toFixed(1)}%` : '—', '1Y'],
                [a.expense_ratio_pct != null ? `${a.expense_ratio_pct.toFixed(2)}%` : '—', 'TER'],
              ] as [string, string][]).map(([v, l]) => (
                <div key={l} className="rounded-lg bg-surface-2 px-1 py-2 text-center">
                  <div className="font-mono text-[13px] font-bold text-ink">{v}</div>
                  <div className="mt-0.5 text-[9px] font-semibold uppercase text-ink-muted">{l}</div>
                </div>
              ))}
            </div>
            <button type="button" className="w-full rounded-lg bg-surface-2 py-2.5 text-caption font-semibold text-ink-secondary transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">⇄ Add to comparison</button>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
      {ALTS.map((a) => (
        <div key={a.name} className="rounded-2xl border border-line p-4">
          <div className="text-[13.5px] font-bold leading-tight text-ink">{a.name}</div>
          <div className="mt-0.5 text-[11px] text-ink-muted">{a.amc}</div>
          <div className="my-3 grid grid-cols-3 gap-2">
            {([[STRENGTH_WORD[toStrength(a.strengthScore)], 'Read'], [a.ret, '3Y'], [a.exp, 'Exp']] as [string, string][]).map(([v, l]) => (
              <div key={l} className="rounded-lg bg-surface-2 px-1 py-2 text-center">
                <div className={cn('font-mono text-[13px] font-bold', l === 'Exp' ? 'text-ink' : 'text-emerald')}>{v}</div>
                <div className="mt-0.5 text-[9px] font-semibold uppercase text-ink-muted">{l}</div>
              </div>
            ))}
          </div>
          <button type="button" className="w-full rounded-lg bg-surface-2 py-2.5 text-caption font-semibold text-ink-secondary transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">⇄ Add to comparison</button>
        </div>
      ))}
    </div>
  );
}

// ── S22 — AI insights ────────────────────────────────────────────────────────
export function AiInsightsSection({ items, disclosure, notAdvice }: { items?: string[]; disclosure?: string; notAdvice?: string }) {
  if (items) {
    return items.length > 0 ? (
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {items.map((item) => <div key={item} className="rounded-2xl border border-line bg-surface p-4 text-small text-ink-secondary"><RichText text={item} /></div>)}
        </div>
        <DisclosureBundle disclosure={disclosure} notAdvice={notAdvice || 'For education only — not investment advice.'} />
      </div>
    ) : <EmptyState title="AI insights unavailable" description="No validated comparison insights are available for this request." />;
  }
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {AI_INSIGHTS.map((t, i) => (
        <div key={i} className="flex gap-3 rounded-2xl border border-line p-4" style={{ background: 'linear-gradient(135deg,#FAFBFF,#fff)' }}>
          <div className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-xl" style={{ background: 'rgba(139,92,246,.10)', color: '#8B5CF6' }} aria-hidden="true">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3 L13.5 9 L19 10.5 L13.5 12 L12 18 L10.5 12 L5 10.5 L10.5 9 Z" /></svg>
          </div>
          <div className="text-small leading-relaxed text-ink-secondary"><RichText text={t} /></div>
        </div>
      ))}
    </div>
  );
}

// ── S23 — FAQ ────────────────────────────────────────────────────────────────
function FaqItem({ q, a, defaultOpen }: { q: string; a: string; defaultOpen?: boolean }) {
  const [open, setOpen] = React.useState(!!defaultOpen);
  return (
    <div className="border-b border-line last:border-b-0">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="flex w-full items-center justify-between gap-3 py-3.5 text-left text-sm font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
        {q}<span className={cn('shrink-0 text-ink-muted transition-transform', open && 'rotate-180')} aria-hidden="true">▾</span>
      </button>
      {open && <div className="max-w-[820px] pb-4 text-small leading-relaxed text-ink-muted">{a}</div>}
    </div>
  );
}
export function FaqSection() {
  return (
    <Panel>
      {FAQ.map(([q, a], i) => <FaqItem key={q} q={q} a={a} defaultOpen={i === 0} />)}
    </Panel>
  );
}

// ── S24 — Sticky decision bar ────────────────────────────────────────────────
export function StickyBar() {
  return (
    <div className="fixed inset-x-0 bottom-0 z-[55] border-t border-white/10 shadow-[0_-8px_30px_rgba(0,0,0,.18)]" style={{ background: 'rgba(11,31,58,.97)', backdropFilter: 'blur(12px)' }}>
      <div className="mx-auto flex max-w-6xl items-center gap-5 px-4 py-2.5 text-white sm:px-6">
        <div className="flex shrink-0 items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl text-xl" style={{ background: 'rgba(16,185,129,.18)' }} aria-hidden="true">🏆</div>
          <div>
            <div className="text-[9px] font-semibold uppercase tracking-[0.07em] text-slate-400">DhanRadar read</div>
            <div className="text-[17px] font-extrabold leading-tight tracking-tight text-emerald-300">{STICKY.name}</div>
            <div className="hidden text-[11px] text-slate-300 sm:block">{STICKY.meta}</div>
          </div>
        </div>
        <div className="ml-auto hidden gap-6 lg:flex">
          {STICKY.stats.map(([v, l]) => (
            <div key={l} className="text-center">
              <div className="font-mono text-sm font-bold">{v}</div>
              <div className="mt-0.5 text-[9.5px] font-semibold uppercase tracking-[0.05em] text-slate-400">{l}</div>
            </div>
          ))}
        </div>
        <div className="flex shrink-0 gap-2">
          <CTA variant="ghost" className="border-white/20 bg-white/10 text-white hover:bg-white/20">☆ Watchlist</CTA>
          <CTA variant="primary">View Bandhan</CTA>
        </div>
      </div>
    </div>
  );
}

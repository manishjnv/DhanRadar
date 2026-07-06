/**
 * Fund Detail V3 — COMPLIANCE-CRITICAL sections (authored + reviewed on Opus).
 *
 * Every score/label/confidence surface here is translated to the educational,
 * no-numeric form (non-neg #1, #2):
 *   - Hero / Score Breakdown: band-ring (colour=label, fill=confidence band),
 *     NEVER a 0–100 number; factors are strength WORDS.
 *   - Verdict / Sticky bar: educational LABEL word (In Form / On Track …) and a
 *     confidence BAND word — never "Strong Buy" or a "%confidence" number.
 *   - Mood: real regime WORD (GET /market/mood). Entry timing: no valuation
 *     source exists yet — an educational explainer + honest no-data state.
 * Action CTAs keep the "Invest / SIP" labels (founder call 2026-06-24).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';
import { FundAvatar } from '@/components/mf/explore/FundAvatar';
import { MoodGauge } from '@/components/mood/MoodGauge';
import { useMoodCurrent } from '@/features/mood/api';
import type { MoodFactor, MoodTrend } from '@/features/mood/types';
import { DataState } from '@/components/ui/DataState';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import {
  HeroRing, StrengthBar, WhatThisMeans, Panel, LiveBadge,
} from './parts';
import {
  FUND, VERDICT, NO_DATA_FACTOR_TILES,
} from './sampleData';
import { getCategoryAboutCopy, getStickyCategoryStats } from './categoryCopy';
import type { Strength } from './sampleData';

// W2 (§10.1): the engine's named confidence-quality bands (consistency/recency/
// volatility/data_coverage today) — band words only, never a number (non-neg #2).
// NOT the frozen quality/valuation/momentum/risk/trend score axes (the engine
// does not expose a per-axis band; see the W2 report deviations).
export type FundFactors = Record<string, 'high' | 'medium' | 'low'> | null;
export interface FundSignalWords {
  contributing: string[];
  contradicting: string[];
}

const BAND_STRENGTH: Record<'high' | 'medium' | 'low', Strength> = {
  high: 'strong', medium: 'moderate', low: 'soft',
};
const BAND_RING_COLOR: Record<'high' | 'medium' | 'low', string> = {
  high: '#00B386', medium: '#F5A623', low: '#64748B',
};

/** "data_coverage" → "Data Coverage" — no hardcoded name map; any engine key renders. */
function factorDisplayName(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

// Label → display + ring/text colour (mirrors ScoreRing/FundScoreCell canon).
const LABEL_DISPLAY: Record<Label, string> = {
  in_form: 'In Form', on_track: 'On Track', off_track: 'Off Track',
  out_of_form: 'Out of Form', insufficient_data: 'Insufficient Data',
};
const LABEL_STROKE: Record<Label, string> = {
  in_form: '#00B386', on_track: '#00C2FF', off_track: '#F5A623',
  out_of_form: '#E5484D', insufficient_data: '#6B7280',
};
const BAND_WORD: Record<ConfidenceBand, string> = { high: 'High', medium: 'Medium', low: 'Low' };

/** Rank presented as a percentile BAND, not a bare "#3/24" badge (§16.2 differentiator —
 * counters the leaderboard framing rivals use). Rank ordinals are DOM-allowed (§9). */
function percentileBandCaption(rank: number, total: number): string {
  const pct = rank / total;
  if (pct <= 0.1) return 'Top 10% of category';
  if (pct <= 0.25) return 'Top 25% of category';
  if (pct <= 0.5) return 'Top half of category';
  return 'Bottom half of category';
}

const NAVY_GRADIENT = 'linear-gradient(115deg, var(--dr-navy,#0B1F3A) 0%, #13294F 48%, #1E3A6E 100%)';
const EMERALD_GRADIENT = 'linear-gradient(135deg, #052E26 0%, #064E3B 70%)';

export interface FundHead {
  name: string;
  amc: string | null;
  category: string;
  label: Label;
  band: ConfidenceBand | null;
  // null when the fund has no mf_fund_ranks row yet (unranked — W0 gate: any ISIN loads).
  rank: number | null;
  total: number | null;
  planOption: string[];        // ["Direct", "Growth"]
  aumCr: number | null;        // real AMC-level AUM if present
  // W0 — real hero KPIs (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §17). Null = show "—",
  // never the sampleData preview value (Min SIP·Lumpsum stays preview, source-blocked).
  navLatest: number | null;
  navDate: string | null;
  navChangePct: number | null;
  expenseRatioPct: number | null;
  // S9 Snapshot (this wave) — launch date + the fund's OWN disclosed AUM (SEBI
  // monthly portfolio disclosure grand-total row), distinct from the AMC-level
  // aumCr above which is still source-blocked (B67/ADR-0035).
  launchDate: string | null;
  fundAumCr: number | null;
  fundAumAsOf: string | null;
  // Returns tab (S10 Performance Center) — real period returns; 1M/10Y/Launch stay "—".
  return3mPct: number | null;
  return6mPct: number | null;
  return1yPct: number | null;
  return3yPct: number | null;
  return5yPct: number | null;
}

// ═══════════════════════════════════════════════════════════════════════════
// S1 — HERO
// ═══════════════════════════════════════════════════════════════════════════
export function HeroSection({ head, factors }: { head: FundHead; factors: FundFactors }) {
  const labelWord = LABEL_DISPLAY[head.label];
  const bandWord = head.band ? BAND_WORD[head.band] : null;
  const pills = [
    ...(head.planOption.length ? [head.planOption.join(' · ')] : []),
    ...FUND.pills,
  ];

  return (
    <header className="relative overflow-hidden rounded-3xl px-6 py-6 text-white shadow-lg sm:px-7" style={{ background: NAVY_GRADIENT }}>
      <div aria-hidden="true" className="pointer-events-none absolute -right-12 -top-24 h-80 w-80 rounded-full" style={{ background: 'radial-gradient(circle, rgba(30,94,255,.34), transparent 68%)' }} />
      <div className="relative grid gap-7 lg:grid-cols-[1fr_300px]">
        {/* left */}
        <div className="min-w-0">
          <div className="flex items-center gap-4">
            <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-white shadow-md">
              <span className="text-h3 font-bold" style={{ color: 'var(--dr-navy,#0B1F3A)' }}>{head.name[0]?.toUpperCase() ?? 'F'}</span>
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-h2 font-semibold leading-tight tracking-[-0.02em] text-white">{head.name}</h1>
                {/* dev-verify */}
                <LiveBadge />
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {pills.map((p) => (
                  <span key={p} className="rounded-full bg-white/[0.12] px-2.5 py-1 text-caption font-semibold text-white/90">{p}</span>
                ))}
                <span className="rounded-full bg-amber/[0.22] px-2.5 py-1 text-caption font-semibold text-amber">⚠ {FUND.riskBand}</span>
                {head.rank != null && head.total != null && (
                  <span className="rounded-full bg-emerald/[0.22] px-2.5 py-1 text-caption font-semibold text-emerald">★ Rank {head.rank} / {head.total}</span>
                )}
              </div>
            </div>
          </div>

          {/* KPI strip — NAV/AUM/Expense Ratio are real (W0); "—" when not present.
              Min SIP · Lumpsum stays preview (source-blocked, §11). */}
          <div className="mt-5 grid grid-cols-2 gap-3.5 border-t border-white/10 pt-4 sm:grid-cols-4">
            <HeroKpi
              l={head.navDate ? `NAV · ${new Date(head.navDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}` : 'NAV'}
              v={head.navLatest != null ? `₹${head.navLatest.toFixed(2)}` : '—'}
              sub={head.navChangePct != null ? `${head.navChangePct >= 0 ? '▲' : '▼'}${Math.abs(head.navChangePct).toFixed(2)}%` : undefined}
              subTone={head.navChangePct != null ? head.navChangePct >= 0 : undefined}
            />
            <HeroKpi l="AUM" v={head.aumCr != null ? `₹${head.aumCr.toLocaleString('en-IN', { maximumFractionDigits: 0 })} Cr` : '—'} />
            <HeroKpi l="Expense Ratio" v={head.expenseRatioPct != null ? `${head.expenseRatioPct.toFixed(2)}%` : '—'} />
            <HeroKpi l="Min SIP · Lumpsum" v={FUND.minSip} sub={`· ${FUND.minLump}`} />
          </div>

          {/* actions — Invest / SIP labels kept per founder call */}
          <div className="mt-4 flex flex-wrap gap-2">
            <CTA kind="invest">⚡ Invest Now</CTA>
            <CTA kind="sip">＋ Start SIP</CTA>
            <CTA kind="ghost">⇄ Compare</CTA>
            <CTA kind="ghost">☆ Watchlist</CTA>
            <CTA kind="ghost">↗ Share</CTA>
          </div>
        </div>

        {/* right — assessment card (band ring, NO number) */}
        <div className="flex flex-col items-center rounded-2xl border border-white/10 bg-white/[0.07] p-4.5" style={{ padding: 18 }}>
          <HeroRing
            color={LABEL_STROKE[head.label]}
            band={head.band}
            size={118}
            onDark
            centerWord={
              <div className="text-center">
                <div className="text-body font-bold leading-none text-white">{labelWord}</div>
                <div className="mt-1 font-mono text-[10px] text-white/55">{bandWord ? `${bandWord} confidence` : 'confidence n/a'}</div>
              </div>
            }
          />
          {/* Standing badge is preview copy — hidden for unranked funds so it can't contradict "Not yet ranked". */}
          {head.rank != null && (
            <div className="mt-2 rounded-full bg-emerald/20 px-3 py-1 text-small font-bold text-emerald">✦ {FUND.standing}</div>
          )}
          <div className="mt-1.5 text-caption text-white/75">
            {head.rank != null && head.total != null ? `Rank ${head.rank} of ${head.total} in category` : 'Not yet ranked in category'}
          </div>
          {head.rank != null && head.total != null && (
            <div className="mt-0.5 font-mono text-[10px] text-white/55">
              {percentileBandCaption(head.rank, head.total)}
            </div>
          )}
          <div className="mt-3.5 flex w-full items-center justify-between border-t border-white/10 pt-3">
            <span className="font-mono text-[10px] uppercase tracking-wide text-white/55">Assessment factors</span>
          </div>
          <div className="mt-2.5 flex w-full flex-col gap-1.5">
            {factors && Object.keys(factors).length > 0 ? (
              Object.entries(factors).map(([key, band]) => (
                <StrengthBar key={key} name={factorDisplayName(key)} strength={BAND_STRENGTH[band]} onDark />
              ))
            ) : (
              <p className="m-0 text-caption text-white/60">Not yet rated — not enough data for an assessment yet.</p>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

function HeroKpi({ l, v, sub, subTone }: { l: string; v: string; sub?: string; subTone?: boolean }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wide text-white/55">{l}</div>
      <div className="mt-1 font-mono text-body font-bold text-white">
        {v}{sub && <span className={cn('ml-1 text-caption font-medium', subTone ? 'text-emerald' : 'text-white/70')}>{sub}</span>}
      </div>
    </div>
  );
}

function CTA({ kind, children }: { kind: 'invest' | 'sip' | 'ghost'; children: React.ReactNode }) {
  const base = 'inline-flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-small font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50 whitespace-nowrap';
  if (kind === 'invest') return <button className={cn(base, 'bg-royal text-white hover:opacity-90')} style={{ background: 'var(--dr-royal,#1E5EFF)' }}>{children}</button>;
  if (kind === 'sip') return <button className={cn(base, 'bg-white hover:bg-surface-2')} style={{ color: 'var(--dr-navy,#0B1F3A)' }}>{children}</button>;
  return <button className={cn(base, 'border border-white/20 bg-white/10 text-white hover:bg-white/20')}>{children}</button>;
}

// ═══════════════════════════════════════════════════════════════════════════
// S1b — STATUS BADGE ROW (W2: real contributing signals, first 3 — §10.1)
// ═══════════════════════════════════════════════════════════════════════════
export function StatusRow({ contributing }: { contributing: string[] }) {
  const badges = contributing.slice(0, 3);
  // no-suppress rule: an empty read still renders, as an honest no-data line.
  if (badges.length === 0) {
    return (
      <p className="mt-3.5 text-caption text-ink-muted">Not enough data yet for a highlights row.</p>
    );
  }
  return (
    <div className="mt-3.5 flex flex-wrap gap-2">
      {badges.map((text) => (
        <span key={text} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-caption font-semibold text-ink shadow-sm">
          <span className="grid h-4 w-4 place-items-center rounded-full bg-emerald text-[9px] text-white">✓</span>
          {text}
        </span>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S2 — EDUCATIONAL VERDICT (label word, not "Strong Buy")
// ═══════════════════════════════════════════════════════════════════════════
export function VerdictSection({ head, signals }: { head: FundHead; signals: FundSignalWords }) {
  const labelWord = LABEL_DISPLAY[head.label];
  const bandWord = head.band ? BAND_WORD[head.band] : null;
  const fill = head.band === 'high' ? 85 : head.band === 'medium' ? 55 : head.band === 'low' ? 30 : 60;
  return (
    <section className="relative overflow-hidden rounded-3xl px-6 py-6 text-white shadow-lg sm:px-7" style={{ background: EMERALD_GRADIENT }}>
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-16 -right-10 h-64 w-64 rounded-full" style={{ background: 'radial-gradient(circle, rgba(16,185,129,.3), transparent 70%)' }} />
      <div className="relative flex flex-wrap items-start gap-5">
        <div className="shrink-0">
          <div className="font-mono text-caption font-bold uppercase tracking-[0.1em] text-emerald">{VERDICT.tag}</div>
          <div className="mt-1.5 text-h1 font-semibold leading-none tracking-[-0.03em] text-white">{labelWord}</div>
          <div className="mt-3 flex items-center gap-2.5">
            <span className="h-[7px] w-[130px] overflow-hidden rounded bg-white/15">
              <span className="block h-full rounded" style={{ width: `${fill}%`, background: 'linear-gradient(90deg,#34D399,#A7F3D0)' }} />
            </span>
            <span className="font-mono text-small font-bold text-white">{bandWord ? `${bandWord} confidence` : 'Confidence n/a'}</span>
          </div>
        </div>
        <p className="min-w-[240px] flex-1 text-body leading-relaxed text-emerald-50" style={{ color: '#D1FAE5' }}>{VERDICT.summary}</p>
      </div>
      <div className="relative mt-5 grid gap-6 border-t border-white/15 pt-4 sm:grid-cols-2">
        <div>
          <h5 className="m-0 mb-2.5 font-mono text-caption font-bold uppercase tracking-wide text-emerald">✓ What&apos;s going well</h5>
          {signals.contributing.length > 0 ? (
            signals.contributing.map((s) => (
              <div key={s} className="mb-2 flex gap-2 text-small leading-snug" style={{ color: '#D1FAE5' }}>
                <span className="shrink-0 font-bold text-emerald">✓</span>{s}
              </div>
            ))
          ) : (
            <p className="m-0 text-small leading-snug" style={{ color: '#D1FAE5' }}>Not enough data yet to name specific strengths.</p>
          )}
        </div>
        <div>
          <h5 className="m-0 mb-2.5 font-mono text-caption font-bold uppercase tracking-wide" style={{ color: '#FCA5A5' }}>✗ What to watch</h5>
          {signals.contradicting.length > 0 ? (
            signals.contradicting.map((s) => (
              <div key={s} className="mb-2 flex gap-2 text-small leading-snug" style={{ color: '#FED7D7' }}>
                <span className="shrink-0 font-bold" style={{ color: '#FCA5A5' }}>✗</span>{s}
              </div>
            ))
          ) : (
            <p className="m-0 text-small leading-snug" style={{ color: '#FED7D7' }}>No specific concerns flagged yet.</p>
          )}
        </div>
      </div>
      {/* About this category — static per-category-class copy (§16.2 table-stakes) */}
      <p className="relative mt-5 border-t border-white/15 pt-4 text-caption leading-relaxed" style={{ color: '#D1FAE5' }}>
        <b className="font-semibold text-white">About this category:</b> {getCategoryAboutCopy(head.category)}
      </p>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S3 — SMART ENTRY TIMING (honest: no index/category valuation source exists
// yet, §18.1 — an educational explainer + the standard no-data state, never a
// fabricated valuation meter). No LiveBadge — nothing here is wired to data.
// ═══════════════════════════════════════════════════════════════════════════
export function EntryTimingSection() {
  return (
    <Panel className="p-4 sm:p-5">
      <p className="text-small leading-relaxed text-ink-secondary">
        Entry timing looks at how richly or cheaply a fund&apos;s category/index is valued —
        long-term investors sometimes use it to decide between a lumpsum and spreading
        purchases out over a few months (SIP or staggered tranches).
      </p>
      <div className="mt-3.5">
        <EmptyState
          title="Not available yet"
          description="We don't have index valuation data yet for this fund's category."
          className="py-6"
        />
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S6 — MARKET MOOD ANALYSIS — real GET /market/mood (useMoodCurrent), same
// regime word/gauge/vocabulary as /mood (shared MoodGauge component + the
// same REGIME_DISPLAY word set). Per-fund phase-performance history isn't
// recorded yet — an honest no-data note, never the old sample numbers.
// ═══════════════════════════════════════════════════════════════════════════
const MOOD_TREND_DISPLAY: Record<MoodTrend, { label: string; cls: string }> = {
  improving: { label: 'Improving', cls: 'text-emerald bg-emerald/10' },
  stable: { label: 'Stable', cls: 'text-ink-secondary bg-surface-2' },
  deteriorating: { label: 'Cooling', cls: 'text-amber bg-amber/10' },
};

function MoodFactorList({ title, items, tone }: { title: string; items: MoodFactor[]; tone: 'up' | 'down' }) {
  // no-suppress-ok: optional sub-list inside the still-mounted MoodSection (mirrors MarketMoodSection.tsx's FactorList)
  if (!items.length) return null;
  return (
    <div>
      <h5 className={cn('mb-1.5 text-caption font-semibold uppercase tracking-wide', tone === 'up' ? 'text-emerald' : 'text-amber')}>
        {title}
      </h5>
      <ul className="flex flex-col gap-1">
        {items.map((item) => (
          <li key={item.label} className="flex gap-1.5 text-caption leading-relaxed text-ink-secondary">
            <span aria-hidden="true" className={tone === 'up' ? 'text-emerald' : 'text-amber'}>•</span>
            <span className={item.tier === 'strong' ? 'font-medium text-ink' : undefined}>{item.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MoodSection() {
  const { data, isLoading, isError } = useMoodCurrent();
  const unavailable = !data || data.data_quality === 'unavailable' || data.regime === 'data_unavailable';
  const status = isLoading ? 'loading' : isError ? 'error' : unavailable ? 'empty' : 'present';
  const trend = data?.trend ? MOOD_TREND_DISPLAY[data.trend] : null;

  return (
    <Panel className="p-5 sm:p-6">
      <DataState
        status={status}
        emptyCopy="The daily mood snapshot updates after market close — check back shortly."
        skeleton={<Skeleton className="h-40 w-full rounded-2xl" />}
      >
        {data && (
          <div className="grid items-center gap-6 md:grid-cols-[230px_1fr]">
            <div className="flex flex-col items-center gap-2">
              <MoodGauge regime={data.regime} confidenceBand={data.confidence_band} />
              {trend && (
                <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-caption font-semibold', trend.cls)}>
                  Trend: {trend.label}
                </span>
              )}
            </div>
            <div>
              {data.commentary && (
                <p className="mb-3.5 text-small leading-relaxed text-ink-secondary">{data.commentary}</p>
              )}
              <div className="grid gap-3 sm:grid-cols-2">
                <MoodFactorList title="Supporting the read" items={data.contributing_factors} tone="up" />
                <MoodFactorList title="Counter-signals" items={data.contradicting_factors} tone="down" />
              </div>
            </div>
          </div>
        )}

        <div className="mt-4 rounded-2xl border border-dashed border-line bg-surface-2 p-3.5 text-caption text-ink-muted">
          How this fund has performed across past market-mood regimes isn&apos;t available yet —
          we started recording regime history on 5 Jul 2026, so there isn&apos;t enough of it yet
          for a reliable read.
        </div>

        <WhatThisMeans>
          Market mood describes current investor sentiment — it is not a prediction of what
          markets will do next. Mood is not direction.
        </WhatThisMeans>
      </DataState>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S11 — SCORE BREAKDOWN (W2, §10.1: real factor tiles, band rings, NO numbers)
// ═══════════════════════════════════════════════════════════════════════════
export function ScoreBreakdownSection({ factors }: { factors: FundFactors }) {
  const entries = factors ? Object.entries(factors) : [];
  return (
    <div className="grid gap-3.5 sm:grid-cols-2 2xl:grid-cols-4">
      {entries.length === 0 && (
        <div className="col-span-full rounded-2xl border border-dashed border-line bg-surface-2 p-4 text-caption text-ink-muted">
          Not yet rated — this fund doesn&apos;t have enough data for an assessment yet.
        </div>
      )}
      {entries.map(([key, band]) => (
        <div key={key} className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <HeroRing color={BAND_RING_COLOR[band]} band={band} size={50} stroke={5} onDark={false} />
            <div className="min-w-0 flex-1">
              <div className="text-small font-bold text-ink">{factorDisplayName(key)}</div>
              <div className="mt-0.5 text-caption text-ink-muted">Rank — · Trend —</div>
            </div>
          </div>
          <p className="mt-2.5 border-t border-line pt-2.5 text-caption leading-relaxed text-ink-secondary">
            {BAND_WORD[band]} confidence signal.
          </p>
        </div>
      ))}
      {NO_DATA_FACTOR_TILES.map((name) => (
        <div key={name} className="rounded-2xl border border-dashed border-line bg-surface-2 p-4">
          <div className="text-small font-bold text-ink-muted">{name}</div>
          <p className="mt-2.5 border-t border-line pt-2.5 text-caption leading-relaxed text-ink-faint">
            No data yet — this signal isn&apos;t built for this fund yet.
          </p>
        </div>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S22 — STICKY DECISION BAR (educational label, not advisory)
// ═══════════════════════════════════════════════════════════════════════════
export function StickyBar({ head, topReason }: { head: FundHead; topReason: string | null }) {
  const labelWord = LABEL_DISPLAY[head.label];
  const bandWord = head.band ? BAND_WORD[head.band] : null;
  // Per-category-class static educational copy (§5 row 22, W1). "Top reason" is now
  // the real first contributing signal (W2, §10.1); falls back to a generic
  // educational line when there isn't one yet (unranked / insufficient_data).
  const reason = topReason ?? 'a category-relative educational read';
  const catStats = getStickyCategoryStats(head.category);
  const stickyStats = [
    { v: catStats.horizon, l: 'Horizon' },
    { v: catStats.phase, l: 'Market phase' },
    { v: catStats.approach, l: 'Approach note' },
  ];
  return (
    <div className="fixed inset-x-0 bottom-0 z-50 border-t border-white/10 shadow-[0_-8px_30px_rgba(0,0,0,.18)] backdrop-blur" style={{ background: 'rgba(11,31,58,.97)' }}>
      <div className="flex w-full items-center gap-5 px-4 py-3 text-white sm:px-6 lg:px-8">
        <div className="flex shrink-0 items-center gap-3">
          <div>
            <div className="flex items-center gap-1.5 text-[9.5px] font-semibold uppercase tracking-[0.08em] text-white/55">
              DhanRadar Read
              {/* dev-verify */}
              <LiveBadge />
            </div>
            <div className="text-h3 font-bold leading-none text-emerald">{labelWord}</div>
          </div>
          <div className="hidden text-caption leading-snug text-white/75 sm:block">
            {bandWord ? `${bandWord} confidence` : 'Confidence n/a'}<br />Top reason: <b className="font-mono text-white">{reason}</b>
          </div>
        </div>
        <div className="ml-auto hidden max-w-xl gap-4 xl:flex">
          {stickyStats.map((s) => (
            <div key={s.l} className="w-40 text-left">
              <div className="text-[9px] font-semibold uppercase tracking-wide text-white/55">{s.l}</div>
              <div className="text-[10.5px] leading-snug text-white/85">{s.v}</div>
            </div>
          ))}
        </div>
        <div className="flex shrink-0 gap-2">
          <button className="inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-small font-semibold text-white" style={{ background: 'var(--dr-royal,#1E5EFF)' }}>⚡ Invest</button>
          <button className="inline-flex items-center gap-1.5 rounded-xl bg-white px-4 py-2 text-small font-semibold" style={{ color: 'var(--dr-navy,#0B1F3A)' }}>＋ SIP</button>
        </div>
      </div>
    </div>
  );
}

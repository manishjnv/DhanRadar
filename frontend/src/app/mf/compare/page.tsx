'use client';

/**
 * Fund Comparison page — /mf/compare  (V3)
 *
 * Public educational destination that compares up to 4 mutual funds side-by-side,
 * built to the approved FundComparisonPageV3 desktop + mobile mockups (24
 * sections, fully responsive). Reached from the "⇄ Compare" action on the Fund
 * Detail / Explorer surfaces. No auth required — wrapped in <MaybeShell> so
 * anonymous visitors get clean standalone chrome and logged-in users keep the
 * workspace shell (the V3 destination model, same as Fund Detail V3).
 *
 * DATA (first real slice, 2026-07-13): ?funds=<isin>[,<isin>,<isin>] renders
 * REAL fund tiles (identity + educational label/band + NAV/AUM/TER from
 * fund.head). One ISIN → slots 2-3 auto-fill with the fund's same-category
 * peers (fund.peers — the same feed as Fund Detail's Alternatives section).
 * With 2+ real funds, Performance (S7), Ranking (S10) and Cost (S17) switch to
 * real rows and carry a small LIVE tag; every other section still renders the
 * labelled illustrative PREVIEW until the full comparison feed lands. No
 * param → the original all-sample preview page, unchanged.
 *
 * The two compliance gates that guard the deploy pipeline are honoured:
 * educational labels (no advisory verbs) + band rings / strength words (no raw
 * DhanRadar score in the DOM). Real funds never carry sample badges or the
 * TOP MATCH ribbon, and live-mode "So what" lines are neutral education —
 * never generated winner-picking.
 */

import * as React from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Skeleton } from '@/components/ui/Skeleton';
import { LiveBadge } from '@/components/mf/funddetail/parts';
import {
  HeroSection, EduReadSection, ScoreboardSection,
  MoodSection, PerformanceSection, SipSection, RollingSection, RankingSection,
  RiskSection, FitSection, HoldingsSection, FlowSection, ManagerSection, AmcSection,
  CostSection, TaxSection, ChangesSection, AltsSection,
  AiInsightsSection, FaqSection, StickyBar,
  type SipEntry,
} from '@/components/mf/compare/sections';
import { useCompareBundle } from '@/features/mf/api';
import { FUNDS, type CompareFund, type Row } from '@/components/mf/compare/sampleData';
import type { CompareFragment } from '@/features/mf/types';

function CompareSkeleton() {
  return (
    <div className="flex w-full flex-col gap-6">
      <Skeleton className="h-5 w-64 rounded-full" />
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        <Skeleton className="h-72 rounded-2xl" />
        <Skeleton className="h-72 rounded-2xl" />
        <Skeleton className="h-72 rounded-2xl" />
      </div>
      <Skeleton className="h-44 rounded-3xl" />
    </div>
  );
}

function Crumb({ category, count }: { category: string; count: number }) {
  return (
    <nav className="mb-3.5 flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
      <Link href="/mf/explore" className="hover:text-ink">Mutual Funds</Link>
      <span className="text-ink-faint">›</span>
      <Link href={`/mf/explore?category=${encodeURIComponent(category)}`} className="hover:text-ink">{category}</Link>
      <span className="text-ink-faint">›</span>
      <span className="font-semibold text-ink-secondary">Compare {count} funds</span>
    </nav>
  );
}

function round1(n: number | null): number | null {
  return n == null ? null : Math.round(n * 10) / 10;
}

function fundAgeYears(date: string | null): number | null {
  if (!date) return null;
  const launch = new Date(date);
  if (Number.isNaN(launch.getTime())) return null;
  return (Date.now() - launch.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
}

/** Build a CompareFund display object from a bundle fragment, using slot colours. */
function buildCompareFundFromFragment(frag: CompareFragment, slotIndex: number): CompareFund {
  const slot = FUNDS[slotIndex] ?? FUNDS[0];
  const displayName = frag.fund_name_short ?? frag.scheme_name;
  const years = fundAgeYears(frag.launch_date);
  return {
    key: frag.isin,
    name: displayName,
    short: displayName.split(' ')[0] ?? displayName,
    cat: frag.category ?? frag.sebi_category ?? '—',
    amc: frag.amc_name ?? '—',
    logo: (displayName.charAt(0) || 'F').toUpperCase(),
    color: slot.color,
    topGradient: slot.topGradient,
    label: frag.verb_label ?? 'insufficient_data',
    band: frag.confidence_band ?? 'low',
    assessWord: '',
    nav: frag.nav_latest != null ? frag.nav_latest.toFixed(2) : '—',
    navc: frag.nav_change_pct != null
      ? `${frag.nav_change_pct >= 0 ? '+' : ''}${frag.nav_change_pct.toFixed(2)}%`
      : '',
    aum: frag.aum_crore != null
      ? `${frag.aum_crore.toLocaleString('en-IN', { maximumFractionDigits: 0 })} Cr`
      : '—',
    exp: frag.expense_ratio_pct != null ? `${frag.expense_ratio_pct.toFixed(2)}%` : '—',
    age: years != null ? `${years.toFixed(1)} yrs` : '—',
    mgr: '—',
    badges: [],
    isTopMatch: false,
  };
}

function CompareView() {
  const searchParams = useSearchParams();

  // C1 URL contract: ?isins=; retain ?funds= for backward compat
  const rawIsins = searchParams.get('isins') ?? searchParams.get('funds');
  const isSample = searchParams.has('sample');
  const urlCategory = searchParams.get('category') ?? 'Small Cap';

  // Deduplicate, sort (cache-key stability), cap at 4
  const sortedIsins = React.useMemo(() => {
    if (!rawIsins) return [];
    return [...new Set(rawIsins.split(',').map((s) => s.trim()).filter(Boolean))]
      .sort()
      .slice(0, 4);
  }, [rawIsins]);

  // sample mode: ?sample param OR fewer than 2 valid ISINs
  const sampleMode = isSample || sortedIsins.length < 2;

  // One batch request replaces 3× useFundDetail; disabled in sample mode
  const bundleQuery = useCompareBundle(sampleMode ? [] : sortedIsins);
  const isLoading = !sampleMode && bundleQuery.isLoading;

  // Extract ordered fragments (null fragments excluded)
  const fragments = React.useMemo<CompareFragment[]>(() => {
    if (!bundleQuery.data) return [];
    return sortedIsins
      .map((isin) => bundleQuery.data!.fragments[isin] ?? null)
      .filter((f): f is CompareFragment => f != null);
  }, [bundleQuery.data, sortedIsins]);

  // Live mode requires 2+ resolved fragments
  const live = !sampleMode && fragments.length >= 2;

  const realFunds = React.useMemo<CompareFund[]>(
    () => fragments.map((f, i) => buildCompareFundFromFragment(f, i)),
    [fragments],
  );

  // ── per-section row derivations (all guarded by `live`) ──────────────────

  const perfRows = React.useMemo<Row[] | undefined>(() => {
    if (!live) return undefined;
    return [
      { label: '3M', vals: fragments.map((f) => round1(f.return_3m_pct)), win: 'hi' },
      { label: '6M', vals: fragments.map((f) => round1(f.return_6m_pct)), win: 'hi' },
      { label: '1Y', vals: fragments.map((f) => round1(f.return_1y_pct)), win: 'hi' },
      { label: '3Y', vals: fragments.map((f) => round1(f.return_3y_pct)), win: 'hi' },
      { label: '5Y', vals: fragments.map((f) => round1(f.return_5y_pct)), win: 'hi' },
    ];
  }, [live, fragments]);

  // Category p50 rows appended to the performance table
  const catPerfRows = React.useMemo<Row[] | undefined>(() => {
    if (!live) return undefined;
    return [
      { label: 'Category p50 (1Y)', vals: fragments.map((f) => round1(f.category_median_return_1y_pct)) },
      { label: 'Category p50 (3Y)', vals: fragments.map((f) => round1(f.category_median_return_3y_pct)) },
    ];
  }, [live, fragments]);

  const benchmarkRows = React.useMemo<Row[] | undefined>(() => {
    if (!live) return undefined;
    const rows = ['1y', '3y', '5y'] as const;
    return rows.map((window) => ({
      label: `Benchmark (${fragments[0]?.benchmark_row && !fragments[0].benchmark_row.no_data ? fragments[0].benchmark_row.label : 'unavailable'}) ${window.toUpperCase()}`,
      vals: fragments.map((fragment) => {
        const value = fragment.benchmark_row?.no_data ? null : fragment.benchmark_row.returns[window];
        return value == null ? null : round1(value);
      }),
    }));
  }, [live, fragments]);

  const costRows = React.useMemo<Row[] | undefined>(() => {
    if (!live) return undefined;
    return [
      {
        label: 'Expense ratio',
        vals: fragments.map((f) => (f.expense_ratio_pct != null ? `${f.expense_ratio_pct.toFixed(2)}%` : null)),
        win: 'low',
      },
      {
        label: 'Category median TER',
        vals: fragments.map((f) => (f.category_median_ter_pct != null ? `${f.category_median_ter_pct.toFixed(2)}%` : null)),
      },
      {
        label: 'Fund age',
        vals: fragments.map((f) => {
          const yrs = fundAgeYears(f.launch_date);
          return yrs != null ? `${yrs.toFixed(1)} yrs` : null;
        }),
      },
    ];
  }, [live, fragments]);

  const costVis = React.useMemo<[string, number, string][] | undefined>(() => {
    if (!live) return undefined;
    const gross = Math.pow(1.12, 15);
    const out: [string, number, string][] = [];
    realFunds.forEach((f, i) => {
      const ter = fragments[i]?.expense_ratio_pct;
      if (ter == null) return;
      const feesLakh = (10 * (gross - Math.pow(1 + 0.12 - ter / 100, 15))) / gross;
      out.push([f.short, Math.round(feesLakh * 10) / 10, f.color]);
    });
    return out;
  }, [live, realFunds, fragments]);

  const rankRows = React.useMemo<Row[] | undefined>(() => {
    if (!live) return undefined;
    return [
      {
        label: 'Current rank',
        vals: fragments.map((f) => (f.category_rank != null ? `#${f.category_rank}` : null)),
        win: 'low',
      },
      {
        label: 'Funds in category',
        vals: fragments.map((f) => (f.category_total != null ? String(f.category_total) : null)),
      },
    ];
  }, [live, fragments]);

  const riskRows = React.useMemo<Row[] | undefined>(() => {
    if (!live) return undefined;
    return [
      { label: 'Sharpe ratio', vals: fragments.map((f) => (f.sharpe_ratio != null ? f.sharpe_ratio.toFixed(2) : null)), win: 'hi' },
      { label: 'Sortino ratio', vals: fragments.map((f) => (f.sortino_ratio != null ? f.sortino_ratio.toFixed(2) : null)), win: 'hi' },
      { label: 'Std dev (ann.)', vals: fragments.map((f) => (f.volatility_pct != null ? `${f.volatility_pct.toFixed(2)}%` : null)), win: 'low' },
      { label: 'Max drawdown', vals: fragments.map((f) => (f.max_drawdown_pct != null ? `${f.max_drawdown_pct.toFixed(2)}%` : null)), win: 'low' },
    ];
  }, [live, fragments]);

  const rollingRows = React.useMemo<Row[] | undefined>(() => {
    if (!live) return undefined;
    return [
      { label: '1Y avg return', vals: fragments.map((f) => round1(f.rolling_1y_avg_pct)), win: 'hi' },
      {
        label: '1Y % windows positive',
        vals: fragments.map((f) => (f.rolling_1y_pct_positive != null ? `${Math.round(f.rolling_1y_pct_positive)}%` : null)),
        win: 'hi',
      },
      { label: '3Y avg return', vals: fragments.map((f) => round1(f.rolling_3y_avg_pct)), win: 'hi' },
      {
        label: '3Y % windows positive',
        vals: fragments.map((f) => (f.rolling_3y_pct_positive != null ? `${Math.round(f.rolling_3y_pct_positive)}%` : null)),
        win: 'hi',
      },
    ];
  }, [live, fragments]);

  const scoreboardRows = React.useMemo<Row[] | undefined>(() => {
    if (!live) return undefined;
    return [
      { label: '3Y return', vals: fragments.map((f) => round1(f.return_3y_pct)), win: 'hi' },
      { label: '1Y return', vals: fragments.map((f) => round1(f.return_1y_pct)), win: 'hi' },
      {
        label: 'Expense ratio',
        vals: fragments.map((f) => (f.expense_ratio_pct != null ? `${f.expense_ratio_pct.toFixed(2)}%` : null)),
        win: 'low',
      },
      {
        label: 'Fund age',
        vals: fragments.map((f) => {
          const yrs = fundAgeYears(f.launch_date);
          return yrs != null ? `${yrs.toFixed(1)} yrs` : null;
        }),
      },
      {
        label: 'Max drawdown',
        vals: fragments.map((f) => (f.max_drawdown_pct != null ? `${f.max_drawdown_pct.toFixed(2)}%` : null)),
        win: 'low',
      },
      {
        label: 'Category rank',
        vals: fragments.map((f) => (f.category_rank != null ? `#${f.category_rank}` : null)),
        win: 'low',
      },
    ];
  }, [live, fragments]);

  const sipEntries = React.useMemo<SipEntry[] | undefined>(() => {
    if (!live) return undefined;
    return realFunds.map((fund, i) => ({
      fund,
      sip_5y: fragments[i]?.sip_5y ?? null,
      sip_10y: fragments[i]?.sip_10y ?? null,
    }));
  }, [live, realFunds, fragments]);

  const taxCategories = React.useMemo<string[] | undefined>(() => {
    if (!live) return undefined;
    return fragments.map((f) => f.category ?? f.sebi_category ?? '');
  }, [live, fragments]);

  // C2 depth data is nested inside each public per-ISIN fragment. Pairwise
  // overlap is keyed by the sorted `isin_a|isin_b` pair in the bundle.
  const c2Comp = live
    ? Object.fromEntries(fragments.map((fragment) => [fragment.isin, fragment.composition]))
    : undefined;
  const c2People = live
    ? Object.fromEntries(fragments.map((fragment) => [fragment.isin, fragment.people]))
    : undefined;
  const c2Flows = live
    ? Object.fromEntries(fragments.map((fragment) => [fragment.isin, fragment.flows]))
    : undefined;
  const c2Events = live
    ? Object.fromEntries(fragments.map((fragment) => [fragment.isin, fragment.events.events]))
    : undefined;
  const c2Amc = live
    ? Object.fromEntries(fragments.map((fragment) => [fragment.isin, fragment.amc]))
    : undefined;
  const c2Alts = live
    ? fragments.flatMap((fragment) => fragment.alternatives.peers)
    : undefined;
  const c2Overlap = live && bundleQuery.data?.pairwise
    ? Object.values(bundleQuery.data.pairwise).map((pair) => pair)
    : undefined;

  if (isLoading) return <CompareSkeleton />;

  const count = live ? realFunds.length : 3;
  const category = fragments[0]?.category ?? fragments[0]?.sebi_category ?? urlCategory;
  const heroFunds = live ? realFunds : undefined;

  return (
    <div className="w-full pb-24">
      <div className="mb-4">
        <Link href="/mf/explore" className="mb-3 inline-flex w-fit items-center gap-1 rounded text-small text-ink-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
          ← Back to Fund Explorer
        </Link>
        <Crumb category={category} count={count} />
      </div>

      {/* S1 — Hero comparison columns */}
      <SectionHeader index="01" title={`Comparing ${count} Funds`} info="2–4 funds" badge={live ? <LiveBadge /> : undefined} />
      <HeroSection funds={heroFunds} />

      {/* S2 — DhanRadar educational read (AI wave) */}
      <Section><SectionHeader index="02" title="DhanRadar Educational Read" tag="AI" /><EduReadSection /></Section>

      {/* S3 — Scoreboard */}
      <Section>
        <SectionHeader index="03" title="Quick Comparison Scoreboard" info="Key facts highlighted" badge={live ? <LiveBadge /> : undefined} />
        <ScoreboardSection funds={heroFunds} rows={scoreboardRows} />
      </Section>

      {/* S6 — Market mood */}
      <Section><SectionHeader index="06" title="Market Mood" badge={<LiveBadge />} /><MoodSection /></Section>

      {/* S7 — Performance */}
      <Section>
        <SectionHeader index="07" title="Performance Center" info="Strongest highlighted per period" badge={live ? <LiveBadge /> : undefined} />
        <PerformanceSection rows={perfRows} funds={heroFunds} live={live} catRows={catPerfRows} benchmarkRows={benchmarkRows} />
      </Section>

      {/* S8 — SIP */}
      <Section>
        <SectionHeader index="08" title="SIP Comparison Center" info="Historical illustration" badge={live ? <LiveBadge /> : undefined} />
        <SipSection live={live} entries={sipEntries} />
      </Section>

      {/* S9 — Rolling */}
      <Section>
        <SectionHeader index="09" title="Rolling Returns Comparison" badge={live ? <LiveBadge /> : undefined} />
        <RollingSection rows={rollingRows} live={live} />
      </Section>

      {/* S10 — Ranking */}
      <Section>
        <SectionHeader index="10" title="Ranking Comparison" badge={live ? <LiveBadge /> : undefined} />
        <RankingSection rows={rankRows} funds={heroFunds} live={live} />
      </Section>

      {/* S11 — Risk */}
      <Section>
        <SectionHeader index="11" title="Risk Comparison Center" badge={live ? <LiveBadge /> : undefined} />
        <RiskSection liveRows={riskRows} />
      </Section>

      {/* S12 — Portfolio fit */}
      <Section>
        <SectionHeader index="12" title="Portfolio Fit Comparison" tag="Exclusive" badge={live ? <LiveBadge /> : undefined} />
        <FitSection isins={live ? sortedIsins : undefined} funds={live ? realFunds : undefined} />
      </Section>

      {/* S13 — Holdings */}
      <Section>
        <SectionHeader index="13" title="Portfolio Holdings Comparison" badge={c2Comp || c2Overlap ? <LiveBadge /> : undefined} />
        <HoldingsSection compositions={c2Comp} pairwiseOverlap={c2Overlap} funds={heroFunds} isins={live ? sortedIsins : undefined} />
      </Section>

      {/* S14 — Fund flow */}
      <Section>
        <SectionHeader index="14" title="Fund Flow Intelligence" badge={c2Flows ? <LiveBadge /> : undefined} />
        <FlowSection flows={c2Flows} funds={heroFunds} isins={live ? sortedIsins : undefined} />
      </Section>

      {/* S15 — Managers */}
      <Section>
        <SectionHeader index="15" title="Fund Manager Comparison" badge={c2People ? <LiveBadge /> : undefined} />
        <ManagerSection people={c2People} funds={heroFunds} isins={live ? sortedIsins : undefined} />
      </Section>

      {/* S16 — AMC */}
      <Section>
        <SectionHeader index="16" title="AMC Comparison" badge={c2Amc ? <LiveBadge /> : undefined} />
        <AmcSection amcData={c2Amc} funds={heroFunds} isins={live ? sortedIsins : undefined} />
      </Section>

      {/* S17 — Cost */}
      <Section>
        <SectionHeader index="17" title="Cost Comparison" info="Impact on ₹10 L over time" badge={live ? <LiveBadge /> : undefined} />
        <CostSection rows={costRows} vis={costVis} funds={heroFunds} live={live} />
      </Section>

      {/* S18 — Tax */}
      <Section>
        <SectionHeader index="18" title="Tax Comparison" info="On ₹2 L gain · >1yr" badge={live ? <LiveBadge /> : undefined} />
        <TaxSection categories={taxCategories} />
      </Section>

      {/* S20 — What changed */}
      <Section>
        <SectionHeader index="20" title="What Changed Recently" badge={c2Events ? <LiveBadge /> : undefined} />
        <ChangesSection events={c2Events} funds={heroFunds} isins={live ? sortedIsins : undefined} />
      </Section>

      {/* S21 — Similar funds in this category */}
      <Section>
        <SectionHeader index="21" title="Similar Funds in This Category" info="Excluding compared funds" badge={c2Alts ? <LiveBadge /> : undefined} />
        <AltsSection alternatives={c2Alts} />
      </Section>

      {/* S22 — AI insights */}
      <Section><SectionHeader index="22" title="AI Insights Center" tag="AI" /><AiInsightsSection /></Section>

      {/* S23 — FAQ */}
      <Section><SectionHeader index="23" title="Frequently Asked" /><FaqSection /></Section>

      {/* Disclosure */}
      <div className="mt-7 rounded-2xl border border-line bg-surface-2 p-4">
        <DisclosureBundle notAdvice="For education only — not investment advice. This comparison and figures shown (many illustrative previews while data feeds are built) are educational signals derived from factual data, not recommendations to buy, sell, or hold any fund. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Past performance does not indicate future returns." />
      </div>

      {/* StickyBar */}
      <StickyBar />
    </div>
  );
}

export default function FundComparePage() {
  return (
    <MaybeShell maxWidth="full">
      <React.Suspense fallback={<CompareSkeleton />}>
        <CompareView />
      </React.Suspense>
    </MaybeShell>
  );
}

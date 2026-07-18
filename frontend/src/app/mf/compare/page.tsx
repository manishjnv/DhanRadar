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
import { Preview } from '@/components/mf/compare/ui';
import {
  HeroSection, EduReadSection, ScoreboardSection, PersonaSection, MatrixSection,
  MoodSection, PerformanceSection, SipSection, RollingSection, RankingSection,
  RiskSection, FitSection, HoldingsSection, FlowSection, ManagerSection, AmcSection,
  CostSection, TaxSection, ValuationSection, ChangesSection, AltsSection,
  AiInsightsSection, FaqSection, StickyBar,
} from '@/components/mf/compare/sections';
import { useFundDetail, useFundPeers } from '@/features/mf/api';
import { FUNDS, type CompareFund, type Row } from '@/components/mf/compare/sampleData';
import type { FundHead } from '@/features/mf/types';

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

/** Map a real fund.head onto the sample tile shape. Decoration (color/gradient)
 * comes from the slot; identity/facts are real; sample badges / TOP MATCH /
 * assessWord never attach to a real fund (compliance — no fabricated praise). */
function buildCompareFund(head: FundHead, slotIndex: number): CompareFund {
  const slot = FUNDS[slotIndex] ?? FUNDS[0];
  const displayName = head.fund_name_short ?? head.scheme_name;
  const years = fundAgeYears(head.launch_date);
  return {
    key: head.isin,
    name: displayName,
    short: displayName.split(' ')[0] ?? displayName,
    cat: head.category ?? head.sebi_category ?? '—',
    amc: head.amc_name ?? '—',
    logo: (displayName.charAt(0) || 'F').toUpperCase(),
    color: slot.color,
    topGradient: slot.topGradient,
    label: head.verb_label ?? 'insufficient_data',
    band: head.confidence_band ?? 'low',
    assessWord: '',
    nav: head.nav_latest != null ? head.nav_latest.toFixed(2) : '—',
    navc: head.nav_change_pct != null
      ? `${head.nav_change_pct >= 0 ? '+' : ''}${head.nav_change_pct.toFixed(2)}%`
      : '',
    aum: head.aum_crore != null
      ? `${head.aum_crore.toLocaleString('en-IN', { maximumFractionDigits: 0 })} Cr`
      : '—',
    exp: head.expense_ratio_pct != null ? `${head.expense_ratio_pct.toFixed(2)}%` : '—',
    age: years != null ? `${years.toFixed(1)} yrs` : '—',
    mgr: '—',
    badges: [],
    isTopMatch: false,
  };
}

function CompareView() {
  const searchParams = useSearchParams();
  const rawFunds = searchParams.get('funds');
  const urlCategory = searchParams.get('category') ?? 'Small Cap';

  const realIsins = React.useMemo(() => {
    if (!rawFunds) return [];
    return rawFunds
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .filter((v, i, a) => a.indexOf(v) === i)
      .slice(0, 3);
  }, [rawFunds]);

  // Peers auto-fill: one ISIN → slots 2-3 become the fund's top same-category
  // peers ("ranked nearby" — same feed as Fund Detail's Alternatives section).
  const peersQuery = useFundPeers(realIsins.length === 1 ? realIsins[0] : '');
  const peerIsins = React.useMemo(() => {
    if (realIsins.length !== 1) return ['', ''];
    const peers = peersQuery.data?.data?.peers ?? [];
    const filtered = peers
      .filter((p) => p.isin !== realIsins[0])
      .map((p) => p.isin)
      .filter((v, i, a) => a.indexOf(v) === i);
    return [filtered[0] ?? '', filtered[1] ?? ''];
  }, [peersQuery.data, realIsins]);

  const detailIsins = React.useMemo(() => {
    const arr = [...realIsins];
    if (arr.length === 1) {
      arr.push(peerIsins[0], peerIsins[1]);
    }
    while (arr.length < 3) arr.push('');
    return arr.slice(0, 3);
  }, [realIsins, peerIsins]);

  const q0 = useFundDetail(detailIsins[0]);
  const q1 = useFundDetail(detailIsins[1]);
  const q2 = useFundDetail(detailIsins[2]);

  const detailHeads = React.useMemo(() => [q0.data, q1.data, q2.data], [q0.data, q1.data, q2.data]);
  const isLoading =
    q0.isLoading || q1.isLoading || q2.isLoading ||
    (realIsins.length === 1 && peersQuery.isLoading);

  const realHeads = React.useMemo(
    () => detailHeads.filter((h): h is FundHead => h != null),
    [detailHeads],
  );
  const realFunds = React.useMemo(
    () =>
      detailHeads
        .map((h, i) => (h ? buildCompareFund(h, i) : null))
        .filter((f): f is CompareFund => f != null),
    [detailHeads],
  );

  // Live mode needs 2+ real funds — one real fund inside a sample table would
  // compare real numbers against illustrative ones, which is misleading.
  const live = realHeads.length >= 2;

  const perfRows = React.useMemo<Row[] | undefined>(() => {
    if (!live) return undefined;
    const heads = realHeads;
    return [
      { label: '3M', vals: heads.map((h) => round1(h.return_3m_pct)), win: 'hi' },
      { label: '6M', vals: heads.map((h) => round1(h.return_6m_pct)), win: 'hi' },
      { label: '1Y', vals: heads.map((h) => round1(h.return_1y_pct)), win: 'hi' },
      { label: '3Y', vals: heads.map((h) => round1(h.return_3y_pct)), win: 'hi' },
      { label: '5Y', vals: heads.map((h) => round1(h.return_5y_pct)), win: 'hi' },
    ];
  }, [live, realHeads]);

  const costRows = React.useMemo<Row[] | undefined>(() => {
    if (!live) return undefined;
    const heads = realHeads;
    return [
      {
        label: 'Expense ratio',
        vals: heads.map((h) => (h.expense_ratio_pct != null ? `${h.expense_ratio_pct.toFixed(2)}%` : null)),
        win: 'low',
      },
      {
        label: 'Fund age',
        vals: heads.map((h) => {
          const yrs = fundAgeYears(h.launch_date);
          return yrs != null ? `${yrs.toFixed(1)} yrs` : null;
        }),
      },
    ];
  }, [live, realHeads]);

  // TER drag on a ₹10 L lump-sum over 15 years at a 12% gross CAGR — the same
  // "at similar returns" illustration the sample bars used, now from real TERs.
  const costVis = React.useMemo<[string, number, string][] | undefined>(() => {
    if (!live) return undefined;
    const gross = Math.pow(1.12, 15);
    const out: [string, number, string][] = [];
    realFunds.forEach((f, i) => {
      const ter = realHeads[i]?.expense_ratio_pct;
      if (ter == null) return;
      const feesLakh = (10 * (gross - Math.pow(1 + 0.12 - ter / 100, 15))) / gross;
      out.push([f.short, Math.round(feesLakh * 10) / 10, f.color]);
    });
    return out;
  }, [live, realFunds, realHeads]);

  const rankRows = React.useMemo<Row[] | undefined>(() => {
    if (!live) return undefined;
    const heads = realHeads;
    return [
      {
        label: 'Current rank',
        vals: heads.map((h) => (h.category_rank != null ? `#${h.category_rank}` : null)),
        win: 'low',
      },
      {
        label: 'Funds in category',
        vals: heads.map((h) => (h.category_total != null ? String(h.category_total) : null)),
      },
    ];
  }, [live, realHeads]);

  if (isLoading) return <CompareSkeleton />;

  const count = realFunds.length || 3;
  const category = realHeads[0]?.category ?? realHeads[0]?.sebi_category ?? urlCategory;
  const heroFunds = realFunds.length ? realFunds : undefined;

  return (
    <div className="w-full pb-24">
      <div className="mb-4">
        <Link href="/mf/explore" className="mb-3 inline-flex w-fit items-center gap-1 rounded text-small text-ink-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
          ← Back to Fund Explorer
        </Link>
        <Crumb category={category} count={count} />
      </div>

      {/* S1 — Hero comparison columns */}
      <SectionHeader index="01" title={`Comparing ${count} Funds`} info="Add up to 4" />
      <HeroSection funds={heroFunds} />

      {/* S2 — DhanRadar educational read (was "Comparison Winner") */}
      <Section><SectionHeader index="02" title="DhanRadar Educational Read" tag="AI" /><EduReadSection /></Section>

      {/* S3 — Scoreboard */}
      <Section><SectionHeader index="03" title="Quick Comparison Scoreboard" info="12 modules · strongest highlighted" /><ScoreboardSection /></Section>

      {/* S4 — Who each fund suits */}
      <Section><SectionHeader index="04" title="Who Each Fund Suits" /><PersonaSection /></Section>

      {/* S5 — Decision matrix */}
      <Section><SectionHeader index="05" title="Smart Decision Matrix" tag="DhanRadar" /><MatrixSection /></Section>

      {/* S6 — Market mood */}
      <Section><SectionHeader index="06" title="Market Mood Comparison" tag="DMMI" info={<Preview />} /><MoodSection /></Section>

      {/* S7 — Performance (LIVE with 2+ real funds) */}
      <Section>
        <SectionHeader index="07" title="Performance Center" info="Strongest highlighted per period" badge={live ? <LiveBadge /> : undefined} />
        <PerformanceSection rows={perfRows} funds={heroFunds} live={live} />
      </Section>

      {/* S8 — SIP */}
      <Section><SectionHeader index="08" title="SIP Comparison Center" info={<Preview />} /><SipSection /></Section>

      {/* S9 — Rolling */}
      <Section><SectionHeader index="09" title="Rolling Returns Comparison" /><RollingSection /></Section>

      {/* S10 — Ranking (LIVE with 2+ real funds) */}
      <Section>
        <SectionHeader index="10" title="Ranking Comparison" badge={live ? <LiveBadge /> : undefined} />
        <RankingSection rows={rankRows} funds={heroFunds} live={live} />
      </Section>

      {/* S11 — Risk */}
      <Section><SectionHeader index="11" title="Risk Comparison Center" /><RiskSection /></Section>

      {/* S12 — Portfolio fit */}
      <Section><SectionHeader index="12" title="Portfolio Fit Comparison" tag="Exclusive" info={<Preview />} /><FitSection /></Section>

      {/* S13 — Holdings */}
      <Section><SectionHeader index="13" title="Portfolio Holdings Comparison" info={<Preview />} /><HoldingsSection /></Section>

      {/* S14 — Fund flow */}
      <Section><SectionHeader index="14" title="Fund Flow Intelligence" info={<Preview />} /><FlowSection /></Section>

      {/* S15 — Managers */}
      <Section><SectionHeader index="15" title="Fund Manager Comparison" /><ManagerSection /></Section>

      {/* S16 — AMC */}
      <Section><SectionHeader index="16" title="AMC Quality Comparison" /><AmcSection /></Section>

      {/* S17 — Cost (LIVE with 2+ real funds) */}
      <Section>
        <SectionHeader index="17" title="Cost Comparison" info="Impact on ₹10 L over time" badge={live ? <LiveBadge /> : undefined} />
        <CostSection rows={costRows} vis={costVis} funds={heroFunds} live={live} />
      </Section>

      {/* S18 — Tax */}
      <Section><SectionHeader index="18" title="Tax Comparison" info="On ₹2 L gain · >1yr" /><TaxSection /></Section>

      {/* S19 — Valuation */}
      <Section><SectionHeader index="19" title="Valuation Comparison" info={<Preview />} /><ValuationSection /></Section>

      {/* S20 — What changed */}
      <Section><SectionHeader index="20" title="What Changed Recently" tag="AI" /><ChangesSection /></Section>

      {/* S21 — Alternatives */}
      <Section><SectionHeader index="21" title="Better Alternatives" info="If none of these fit" /><AltsSection /></Section>

      {/* S22 — AI insights */}
      <Section><SectionHeader index="22" title="AI Insights Center" tag="AI" /><AiInsightsSection /></Section>

      {/* S23 — FAQ */}
      <Section><SectionHeader index="23" title="Frequently Asked" /><FaqSection /></Section>

      {/* Disclosure (educational boundary) */}
      <div className="mt-7 rounded-2xl border border-line bg-surface-2 p-4">
        <DisclosureBundle notAdvice="For education only — not investment advice. This comparison, its educational read, and the figures shown (many illustrative previews while data feeds are built) are educational signals derived from factual data, not recommendations to buy, sell, or hold any fund. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Past performance does not indicate future returns." />
      </div>

      {/* S24 — Sticky decision bar */}
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

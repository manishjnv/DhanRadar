/**
 * Calculator Hub V1 — the page body (client).
 *
 * Renders the approved CalculatorHubV1 desktop + mobile mockups: a hub landing
 * (hero, featured, categories, all-calculators, learn, FAQ) and an inert SIP
 * Calculator detail SHELL reached by activating any calculator card. The
 * hub ⇄ detail switch is a local view toggle (mirrors the mockup's
 * showHub/openCalc) — NOT a route change.
 *
 * PURE UI: no calculator engine, no search, no filtering, no API. Every figure
 * is fixed preview seed data; sliders/toggles are static placeholders. The two
 * deploy-gating compliance rules are honoured: no advisory verbs, and no
 * DhanRadar-computed fund score appears in the DOM (the values here are plain
 * calculator illustrations, not fund ratings).
 */
'use client';

import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import {
  Hero, Rail, FeatureCard, CategoryCard, CalcMiniCard, ChipRow, LearnCard, Faq,
  IconTile, Btn, Panel, Kpi, RangeField, ToggleRow, GrowthChart, Donut,
  WhatIfCard, AiCard, RelatedCard, SoWhat,
} from './ui';
import {
  HERO, HERO_CATS, FEATURED, CATEGORIES, FILTER_CHIPS, ALL_CALCS, LEARN, FAQ,
  SIP_DETAIL, SIP_DEFAULTS, SIP_KPIS, SIP_WHATIF, SIP_AI, SIP_TABLE, SIP_RELATED,
  SIP_SERIES, DISCLAIMER_HUB, DISCLAIMER_CALC,
} from './data';

type View = 'hub' | 'calc';

export function CalculatorHub() {
  const [view, setView] = React.useState<View>('hub');

  const openCalc = React.useCallback(() => {
    setView('calc');
    if (typeof window !== 'undefined') window.scrollTo(0, 0);
  }, []);
  const showHub = React.useCallback(() => {
    setView('hub');
    if (typeof window !== 'undefined') window.scrollTo(0, 0);
  }, []);

  return view === 'hub'
    ? <HubView onOpen={openCalc} />
    : <CalcView onBack={showHub} onOpen={openCalc} />;
}

// ── Breadcrumb ───────────────────────────────────────────────────────────────
function Crumb({ current, onHome }: { current?: string; onHome: () => void }) {
  return (
    <nav className="mb-3.5 flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
      <button type="button" onClick={onHome} className="font-semibold text-ink-secondary hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">Calculators</button>
      {current && (
        <>
          <span className="text-ink-faint">›</span>
          <span className="font-semibold text-ink-secondary">{current}</span>
        </>
      )}
    </nav>
  );
}

// ═══════════════════════════════════ HUB ════════════════════════════════════
function HubView({ onOpen }: { onOpen: () => void }) {
  return (
    <div className="w-full pb-16">
      <Crumb onHome={() => {}} />

      {/* S1 — Hero */}
      <Hero
        title={HERO.title}
        subtitle={HERO.subtitle}
        searchPlaceholder={HERO.searchPlaceholder}
        cats={HERO_CATS}
        stats={HERO.stats}
      />

      {/* S2 — Featured */}
      <Section>
        <SectionHeader index="01" title="Featured Calculators" info="Most used by DhanRadar investors" />
        <Rail gridCols="sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {FEATURED.map((f) => <FeatureCard key={f.name} item={f} onOpen={onOpen} />)}
        </Rail>
      </Section>

      {/* S3 — Categories */}
      <Section>
        <SectionHeader index="02" title="Browse by Category" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {CATEGORIES.map((c) => <CategoryCard key={c.name} item={c} onOpen={onOpen} />)}
        </div>
      </Section>

      {/* S4 — All calculators */}
      <Section>
        <SectionHeader index="03" title="All Calculators" info={`${ALL_CALCS.length} calculators`} />
        <div className="mb-4"><ChipRow chips={FILTER_CHIPS} scroll /></div>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {ALL_CALCS.map((c, i) => <CalcMiniCard key={`${c.name}-${i}`} item={c} onOpen={onOpen} />)}
        </div>
      </Section>

      {/* S5 — Learn the basics */}
      <Section>
        <SectionHeader index="04" title="Learn the Basics" tag="Plain English" />
        <Rail gridCols="sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {LEARN.map((l) => <LearnCard key={l.q} emoji={l.emoji} q={l.q} a={l.a} />)}
        </Rail>
      </Section>

      {/* S6 — FAQ */}
      <Section>
        <SectionHeader index="05" title="Calculator FAQ" />
        <Faq items={FAQ} />
      </Section>

      <p className="mx-auto mt-7 max-w-[880px] text-center text-caption leading-relaxed text-ink-faint">{DISCLAIMER_HUB}</p>
    </div>
  );
}

// ═══════════════════════════════ CALC DETAIL ════════════════════════════════
function CalcView({ onBack, onOpen }: { onBack: () => void; onOpen: () => void }) {
  return (
    <div className="w-full pb-24">
      <Crumb current={SIP_DETAIL.title} onHome={onBack} />

      {/* Header */}
      <div className="mb-5 flex items-center gap-3.5">
        <Btn onClick={onBack} aria-label="Back to all calculators" className="shrink-0 px-3.5">←</Btn>
        <IconTile emoji={SIP_DETAIL.emoji} accent="royal" className="h-[54px] w-[54px] shrink-0 text-[25px]" />
        <div>
          <div className="text-[26px] font-medium tracking-[-0.02em] text-ink">{SIP_DETAIL.title}</div>
          <div className="mt-0.5 text-small text-ink-muted">{SIP_DETAIL.sub}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
        {/* INPUT PANEL (inert) */}
        <Panel className="lg:sticky lg:top-[76px]">
          <h3 className="m-0 text-[15px] font-medium text-ink">Your Investment</h3>
          <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the sliders — results update instantly.</p>

          <RangeField label="Monthly SIP" tip="The amount you invest every month" value={SIP_DEFAULTS.monthly} min={500} max={200000} rangeMin={SIP_DEFAULTS.monthlyRangeMin} rangeMax={SIP_DEFAULTS.monthlyRangeMax} presets={SIP_DEFAULTS.sipPresets} />
          <RangeField label="Expected Annual Growth" tip="CAGR — the average yearly return you expect" value={SIP_DEFAULTS.growth} min={1} max={30} rangeMin={SIP_DEFAULTS.growthRangeMin} rangeMax={SIP_DEFAULTS.growthRangeMax} presets={SIP_DEFAULTS.growthPresets} />
          <RangeField label="Investment Period" tip="How many years you'll keep investing" value={SIP_DEFAULTS.years} min={1} max={40} rangeMin={SIP_DEFAULTS.yearsRangeMin} rangeMax={SIP_DEFAULTS.yearsRangeMax} presets={SIP_DEFAULTS.yearPresets} />

          <div className="mb-3.5">
            <ToggleRow title="Step-up SIP" sub="Increase SIP 10% every year" />
          </div>

          <div className="flex gap-2">
            <Btn variant="pri" className="flex-1">Calculate</Btn>
            <Btn aria-label="Reset inputs">Reset</Btn>
            <Btn aria-label="Export results">⬇</Btn>
            <Btn aria-label="Share results">↗</Btn>
          </div>
        </Panel>

        {/* RESULT PANEL */}
        <div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Kpi hero label="Estimated Future Wealth" value={SIP_KPIS.future} sub={SIP_KPIS.futureSub} />
            <Kpi label="Money You Invest" value={SIP_KPIS.invested} sub="Total contributions" />
            <Kpi label="Profit Earned" value={SIP_KPIS.profit} sub="Growth on your money" accent="pos" />
            <Kpi label="Wealth Multiplier" value={SIP_KPIS.multiplier} sub="Your money grows this many times" />
          </div>

          {/* Chart */}
          <Panel className="mt-3.5">
            <div className="mb-1.5 flex items-center justify-between">
              <div className="text-small font-medium text-ink">Growth Over Time</div>
              <div className="text-caption tracking-normal text-ink-muted">Invested vs Wealth</div>
            </div>
            <GrowthChart series={SIP_SERIES} />
            <div className="mt-3 flex flex-wrap gap-4">
              <span className="inline-flex items-center gap-1.5 text-caption tracking-normal text-ink-secondary"><span className="h-2.5 w-2.5 rounded-[3px] bg-royal" />Estimated Wealth</span>
              <span className="inline-flex items-center gap-1.5 text-caption tracking-normal text-ink-secondary"><span className="h-2.5 w-2.5 rounded-[3px] bg-surface-3" />Money Invested</span>
            </div>
          </Panel>

          {/* What if */}
          <Section className="mt-[18px]">
            <SectionHeader index="✦" title="What If…" info="Small changes, big impact" />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {SIP_WHATIF.map((w) => <WhatIfCard key={w.name} {...w} />)}
            </div>
          </Section>

          {/* AI insights */}
          <Section>
            <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {SIP_AI.map((t, i) => <AiCard key={i} text={t} />)}
            </div>
            <div className="mt-3">
              <DisclosureBundle notAdvice="For education only — not investment advice. These insights illustrate how your own inputs change an estimate; they are not recommendations to buy, sell, or hold any fund. Estimates assume a constant annual return, which real markets do not provide." />
            </div>
          </Section>

          {/* Year table */}
          <Section>
            <SectionHeader index="✦" title="Year-by-Year Growth" />
            <div className="max-h-[340px] overflow-auto rounded-[14px] border border-line">
              <table className="w-full border-collapse text-small">
                <thead>
                  <tr>
                    {['Year', 'Invested', 'Wealth', 'Profit', 'Multiple'].map((h, i) => (
                      <th key={h} className={`sticky top-0 z-[2] border-b-2 border-line bg-surface-2 px-3.5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-ink-muted ${i === 0 ? 'text-left' : 'text-right'}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {SIP_TABLE.map((r) => (
                    <tr key={r.year} className="hover:bg-surface-2">
                      <td className="border-b border-line px-3.5 py-2.5 text-left font-semibold text-ink">Year {r.year}</td>
                      <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-semibold text-ink-muted">{r.invested}</td>
                      <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-bold text-ink">{r.wealth}</td>
                      <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-semibold text-emerald">{r.profit}</td>
                      <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-semibold text-ink">{r.mult}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          {/* Donut split */}
          <Section>
            <SectionHeader index="✦" title="Where Your Wealth Comes From" />
            <Panel>
              <div className="flex flex-col items-center gap-5 sm:flex-row">
                <Donut invested={45} profit={80} />
                <div className="flex-1 self-stretch">
                  <div className="flex items-center gap-2.5 border-b border-line py-2.5">
                    <span className="h-3 w-3 rounded-[3px] bg-surface-3" />
                    <span className="flex-1 text-small font-semibold text-ink">Money You Invest</span>
                    <span className="font-mono font-bold text-ink">{SIP_KPIS.invested}</span>
                    <span className="w-12 text-right font-mono text-ink-muted">{100 - SIP_KPIS.profitPct}%</span>
                  </div>
                  <div className="flex items-center gap-2.5 py-2.5">
                    <span className="h-3 w-3 rounded-[3px] bg-royal" />
                    <span className="flex-1 text-small font-semibold text-ink">Profit Earned</span>
                    <span className="font-mono font-bold text-emerald">{SIP_KPIS.profit}</span>
                    <span className="w-12 text-right font-mono text-ink-muted">{SIP_KPIS.profitPct}%</span>
                  </div>
                  <SoWhat>
                    <b className="font-semibold text-ink">{SIP_KPIS.profitPct}% of your final wealth is pure profit</b> — the power of compounding. The longer you stay invested, the more this share grows.
                  </SoWhat>
                </div>
              </div>
            </Panel>
          </Section>

          {/* Related */}
          <Section>
            <SectionHeader index="✦" title="Related Calculators" />
            <Rail gridCols="sm:grid-cols-2 lg:grid-cols-4">
              {SIP_RELATED.map((r) => <RelatedCard key={r.name} {...r} onOpen={onOpen} />)}
            </Rail>
          </Section>
        </div>
      </div>

      <p className="mx-auto mt-7 max-w-[880px] text-center text-caption leading-relaxed text-ink-faint">{DISCLAIMER_CALC}</p>

      {/* Sticky calc bar */}
      <div className="fixed bottom-[18px] left-1/2 z-[55] flex -translate-x-1/2 items-center gap-3.5 rounded-2xl bg-navy/95 px-4 py-3 shadow-[0_24px_60px_-20px_rgba(15,23,42,.45)] backdrop-blur">
        <div className="text-white">
          <small className="block text-[10px] font-semibold uppercase tracking-[0.04em] text-slate-400">Future Wealth</small>
          <span className="text-small font-bold">{SIP_KPIS.future}</span>
        </div>
        <Btn variant="pri" className="px-3.5">Calculate</Btn>
        <button type="button" className="hidden rounded-[11px] border border-white/15 bg-white/10 px-3.5 py-2.5 text-small font-semibold text-white sm:inline-flex">⬇ Export</button>
        <button type="button" className="hidden rounded-[11px] border border-white/15 bg-white/10 px-3.5 py-2.5 text-small font-semibold text-white sm:inline-flex">↗ Share</button>
      </div>
    </div>
  );
}

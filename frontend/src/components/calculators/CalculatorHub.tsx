/**
 * Calculator Hub V1 — the page body (client).
 *
 * Renders the approved CalculatorHubV1 mockups: a hub landing (hero, featured,
 * categories, all-calculators, learn, FAQ) and a calculator detail view reached
 * by activating any calculator card. The hub ⇄ detail switch is a local view
 * toggle (mirrors the mockup's showHub/openCalc) — NOT a route change.
 *
 * The SIP detail is now LIVE — its inputs drive the generic compounding engine
 * (`computeSip`); KPIs, chart, year table, what-if, and AI insights all recompute
 * from the user's own inputs. The other cards currently open this same SIP detail
 * as the first calculator (the remaining 54 are wired in later sessions).
 *
 * COMPLIANCE: the figures here are the USER's own computed numbers (not a
 * DhanRadar fund score) so the no-numeric-in-DOM carve-out applies — same as the
 * live `SipCalculator`. The assumed return is labelled as the user's assumption,
 * the disclaimer + sensitivity (What-If) sit beside the result, and the AI cards
 * are templated from the user's inputs (no LLM call) under the disclosure bundle.
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
  SIP_DETAIL, SIP_RELATED, DISCLAIMER_HUB, DISCLAIMER_CALC,
} from './data';
import { computeSip, formatInr, formatInrShort } from '@/features/learn/calculators/sip-math';

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
// SIP — the first LIVE calculator. Inputs drive `computeSip`; every figure here
// is the user's own illustration, not a fund score.
function CalcView({ onBack, onOpen }: { onBack: () => void; onOpen: () => void }) {
  const [monthly, setMonthly] = React.useState(25_000);
  const [rate, setRate] = React.useState(12);
  const [years, setYears] = React.useState(15);
  const [stepUp, setStepUp] = React.useState(false);

  const stepUpPct = stepUp ? 10 : 0;
  const result = React.useMemo(
    () => computeSip({ monthlySip: monthly, lumpSum: 0, years, annualRatePct: rate, stepUpPct }),
    [monthly, rate, years, stepUpPct],
  );

  const future = result.futureValue;
  const invested = result.totalInvested;
  const profit = result.wealthGained;
  const multiplier = invested > 0 ? future / invested : 0;
  const profitPct = future > 0 ? Math.round((profit / future) * 100) : 0;

  // What-if — re-run the engine with one input nudged; delta vs the current plan.
  const baseInput = { monthlySip: monthly, lumpSum: 0, years, annualRatePct: rate, stepUpPct };
  const fvWith = (patch: Partial<typeof baseInput>) => computeSip({ ...baseInput, ...patch }).futureValue;
  const realValue = future / Math.pow(1.06, Math.max(years, 0));
  const signed = (d: number) => `${d >= 0 ? '+' : '−'}${formatInrShort(Math.abs(d))} vs now`;

  const whatIf = [
    { name: 'Invest ₹5,000 more', val: `${formatInrShort(monthly + 5000)}/mo`, fv: fvWith({ monthlySip: monthly + 5000 }) },
    { name: 'Invest 5 years longer', val: `${years + 5} yrs`, fv: fvWith({ years: years + 5 }) },
    { name: 'Earn 2% more', val: `${rate + 2}%`, fv: fvWith({ annualRatePct: rate + 2 }) },
    { name: 'Earn 2% less', val: `${Math.max(rate - 2, 0)}%`, fv: fvWith({ annualRatePct: Math.max(rate - 2, 0) }) },
    stepUp
      ? { name: 'Without step-up', val: 'flat', fv: fvWith({ stepUpPct: 0 }) }
      : { name: 'Start a 10% step-up', val: '+10%/yr', fv: fvWith({ stepUpPct: 10 }) },
  ].map((s) => ({ name: s.name, val: s.val, result: formatInrShort(s.fv), delta: signed(s.fv - future), up: s.fv >= future }));
  whatIf.push({
    name: 'Worth in today’s money',
    val: '@6% inflation',
    result: formatInrShort(realValue),
    delta: `${formatInrShort(Math.abs(realValue - future))} less`,
    up: false,
  });

  // AI insights — templated from the user's OWN numbers (no LLM call, no advice).
  const dMore = fvWith({ monthlySip: monthly + 5000 }) - future;
  const dLonger = fvWith({ years: years + 5 }) - future;
  const dStep = fvWith({ stepUpPct: 10 }) - future;
  const ai = [
    `**Investing ₹5,000 more each month** changes this estimate by about **${formatInrShort(dMore)}** — often easier than chasing a higher return.`,
    `**Staying invested 5 more years** adds roughly **${formatInrShort(dLonger)}**. Time in the market tends to matter most.`,
    `**At 6% inflation**, this ${formatInrShort(future)} would buy what **${formatInrShort(realValue)}** buys today — plan for real, not just nominal, wealth.`,
    stepUp
      ? 'Your **10% yearly step-up** is doing a lot of the work here — growing the SIP with your income compounds hard.'
      : `**A 10% yearly step-up** could add about **${formatInrShort(dStep)}**, just by raising your SIP as your income grows.`,
  ];

  // Year-by-year table from the engine series (full, scrollable — no omission).
  const rows = result.series
    .filter((p) => p.year >= 1)
    .map((p) => ({
      year: p.year,
      invested: formatInrShort(p.invested),
      wealth: formatInrShort(p.value),
      profit: `+${formatInrShort(Math.max(p.value - p.invested, 0))}`,
      mult: `${p.invested > 0 ? (p.value / p.invested).toFixed(2) : '0.00'}×`,
    }));

  const reset = () => { setMonthly(25_000); setRate(12); setYears(15); setStepUp(false); };

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
        {/* INPUT PANEL (live) */}
        <Panel className="lg:sticky lg:top-[76px]">
          <h3 className="m-0 text-[15px] font-medium text-ink">Your Investment</h3>
          <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the sliders — results update instantly.</p>

          <RangeField
            label="Monthly SIP"
            tip="The amount you invest every month"
            value={monthly}
            min={500}
            max={200000}
            step={500}
            format={formatInr}
            presets={[{ label: '₹5K', value: 5000 }, { label: '₹10K', value: 10000 }, { label: '₹25K', value: 25000 }, { label: '₹50K', value: 50000 }, { label: '₹1L', value: 100000 }]}
            onChange={setMonthly}
          />
          <RangeField
            label="Expected Annual Growth"
            tip="The average yearly return you assume — your choice, not a DhanRadar prediction"
            value={rate}
            min={1}
            max={30}
            step={0.5}
            format={(n) => `${n}%`}
            presets={[{ label: '8%', value: 8 }, { label: '10%', value: 10 }, { label: '12%', value: 12 }, { label: '15%', value: 15 }]}
            onChange={setRate}
          />
          <RangeField
            label="Investment Period"
            tip="How many years you keep investing"
            value={years}
            min={1}
            max={40}
            step={1}
            format={(n) => `${n} ${n === 1 ? 'yr' : 'yrs'}`}
            presets={[{ label: '5y', value: 5 }, { label: '10y', value: 10 }, { label: '15y', value: 15 }, { label: '20y', value: 20 }, { label: '30y', value: 30 }]}
            onChange={setYears}
          />

          <div className="mb-3.5">
            <ToggleRow title="Step-up SIP" sub="Increase SIP 10% every year" on={stepUp} onToggle={() => setStepUp((v) => !v)} />
          </div>

          <div className="flex gap-2">
            <Btn variant="pri" className="flex-1">Calculate</Btn>
            <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
            <Btn aria-label="Export results">⬇</Btn>
            <Btn aria-label="Share results">↗</Btn>
          </div>
        </Panel>

        {/* RESULT PANEL */}
        <div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Kpi hero label="Estimated Future Wealth" value={formatInrShort(future)} sub={`From ₹${monthly.toLocaleString('en-IN')}/month over ${years} ${years === 1 ? 'year' : 'years'}`} />
            <Kpi label="Money You Invest" value={formatInrShort(invested)} sub="Total contributions" />
            <Kpi label="Profit Earned" value={formatInrShort(profit)} sub="Growth on your money" accent="pos" />
            <Kpi label="Wealth Multiplier" value={`${multiplier.toFixed(1)}×`} sub="Your money grows this many times" />
          </div>

          {/* Chart */}
          <Panel className="mt-3.5">
            <div className="mb-1.5 flex items-center justify-between">
              <div className="text-small font-medium text-ink">Growth Over Time</div>
              <div className="text-caption tracking-normal text-ink-muted">Invested vs Wealth</div>
            </div>
            <GrowthChart series={result.series} />
            <div className="mt-3 flex flex-wrap gap-4">
              <span className="inline-flex items-center gap-1.5 text-caption tracking-normal text-ink-secondary"><span className="h-2.5 w-2.5 rounded-[3px] bg-royal" />Estimated Wealth</span>
              <span className="inline-flex items-center gap-1.5 text-caption tracking-normal text-ink-secondary"><span className="h-2.5 w-2.5 rounded-[3px] bg-surface-3" />Money Invested</span>
            </div>
          </Panel>

          {/* What if */}
          <Section className="mt-[18px]">
            <SectionHeader index="✦" title="What If…" info="Small changes, big impact" />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {whatIf.map((w) => <WhatIfCard key={w.name} {...w} />)}
            </div>
          </Section>

          {/* AI insights */}
          <Section>
            <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {ai.map((t, i) => <AiCard key={i} text={t} />)}
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
                  {rows.map((r) => (
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
                <Donut invested={Math.max(invested, 0)} profit={Math.max(profit, 0)} />
                <div className="flex-1 self-stretch">
                  <div className="flex items-center gap-2.5 border-b border-line py-2.5">
                    <span className="h-3 w-3 rounded-[3px] bg-surface-3" />
                    <span className="flex-1 text-small font-semibold text-ink">Money You Invest</span>
                    <span className="font-mono font-bold text-ink">{formatInrShort(invested)}</span>
                    <span className="w-12 text-right font-mono text-ink-muted">{100 - profitPct}%</span>
                  </div>
                  <div className="flex items-center gap-2.5 py-2.5">
                    <span className="h-3 w-3 rounded-[3px] bg-royal" />
                    <span className="flex-1 text-small font-semibold text-ink">Profit Earned</span>
                    <span className="font-mono font-bold text-emerald">{formatInrShort(profit)}</span>
                    <span className="w-12 text-right font-mono text-ink-muted">{profitPct}%</span>
                  </div>
                  <SoWhat>
                    <b className="font-semibold text-ink">{profitPct}% of your estimated wealth is profit</b> — the power of compounding. The longer you stay invested, the more this share tends to grow.
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
          <span className="text-small font-bold">{formatInrShort(future)}</span>
        </div>
        <Btn variant="pri" className="px-3.5">Calculate</Btn>
        <button type="button" className="hidden rounded-[11px] border border-white/15 bg-white/10 px-3.5 py-2.5 text-small font-semibold text-white sm:inline-flex">⬇ Export</button>
        <button type="button" className="hidden rounded-[11px] border border-white/15 bg-white/10 px-3.5 py-2.5 text-small font-semibold text-white sm:inline-flex">↗ Share</button>
      </div>
    </div>
  );
}

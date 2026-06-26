'use client';

/**
 * AccumulationDetail — the config-driven result view for the E1 family
 * (SIP / Lumpsum / Step-up SIP). Inputs come from the calculator's CalcConfig;
 * everything computes from the generic `computeSip` engine.
 *
 * COMPLIANCE: figures are the USER's own computed numbers (not a DhanRadar fund
 * score) so the no-numeric-in-DOM carve-out applies. The assumed return is
 * labelled as the user's assumption, the disclaimer + What-If sensitivity sit
 * beside the result, and the AI cards are templated from the user's own inputs
 * (no LLM call) under the disclosure bundle. No advisory verbs.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, ToggleRow, GrowthChart, Donut, WhatIfCard, AiCard, RelatedCard, SoWhat } from './ui';
import { computeSip, formatInrShort } from '@/lib/finance';
import { type CalcConfig, getConfig, fmtValue, fmtPreset } from './registry';

export function AccumulationDetail({ config }: { config: CalcConfig }) {
  const initVals = React.useCallback(() => {
    const o: Record<string, number> = {};
    config.inputs.forEach((inp) => { o[inp.key] = inp.default; });
    return o;
  }, [config]);

  const [vals, setVals] = React.useState<Record<string, number>>(initVals);
  const [stepUp, setStepUp] = React.useState(config.stepUpDefault);

  const monthly = vals.monthly ?? 0;
  const lumpSum = vals.lumpSum ?? 0;
  const rate = vals.rate ?? 0;
  const years = vals.years ?? 0;
  const stepUpPct = config.stepUp && stepUp ? 10 : 0;

  const result = React.useMemo(
    () => computeSip({ monthlySip: monthly, lumpSum, years, annualRatePct: rate, stepUpPct }),
    [monthly, lumpSum, rate, years, stepUpPct],
  );

  const future = result.futureValue;
  const invested = result.totalInvested;
  const profit = result.wealthGained;
  const multiplier = invested > 0 ? future / invested : 0;
  const profitPct = future > 0 ? Math.round((profit / future) * 100) : 0;

  const baseInput = { monthlySip: monthly, lumpSum, years, annualRatePct: rate, stepUpPct };
  const fvWith = (patch: Partial<typeof baseInput>) => computeSip({ ...baseInput, ...patch }).futureValue;
  const realValue = future / Math.pow(1.06, Math.max(years, 0));
  const signed = (d: number) => `${d >= 0 ? '+' : '−'}${formatInrShort(Math.abs(d))} vs now`;

  const hasMonthly = config.inputs.some((i) => i.key === 'monthly');
  const bump = hasMonthly
    ? { label: 'Invest ₹5,000 more', patch: { monthlySip: monthly + 5000 } as Partial<typeof baseInput>, val: `${formatInrShort(monthly + 5000)}/mo` }
    : { label: 'Add ₹50,000 more', patch: { lumpSum: lumpSum + 50000 } as Partial<typeof baseInput>, val: formatInrShort(lumpSum + 50000) };

  // What-if — re-run the engine with one input nudged; delta vs the current plan.
  const whatIf: { name: string; val: string; fv: number }[] = [
    { name: bump.label, val: bump.val, fv: fvWith(bump.patch) },
    { name: 'Stay invested 5 years longer', val: `${years + 5} yrs`, fv: fvWith({ years: years + 5 }) },
    { name: 'Earn 2% more', val: `${rate + 2}%`, fv: fvWith({ annualRatePct: rate + 2 }) },
    { name: 'Earn 2% less', val: `${Math.max(rate - 2, 0)}%`, fv: fvWith({ annualRatePct: Math.max(rate - 2, 0) }) },
  ];
  if (config.stepUp) {
    whatIf.push(stepUp
      ? { name: 'Without step-up', val: 'flat', fv: fvWith({ stepUpPct: 0 }) }
      : { name: 'Start a 10% step-up', val: '+10%/yr', fv: fvWith({ stepUpPct: 10 }) });
  }
  const whatIfCards = whatIf.map((s) => ({ name: s.name, val: s.val, result: formatInrShort(s.fv), delta: signed(s.fv - future), up: s.fv >= future }));
  whatIfCards.push({ name: 'Worth in today’s money', val: '@6% inflation', result: formatInrShort(realValue), delta: `${formatInrShort(Math.abs(realValue - future))} less`, up: false });

  // AI insights — templated from the user's OWN numbers (no LLM call, no advice).
  const dLonger = fvWith({ years: years + 5 }) - future;
  const dStep = fvWith({ stepUpPct: 10 }) - future;
  const ai = [
    `**${bump.label}** changes this estimate by about **${formatInrShort(fvWith(bump.patch) - future)}** — small, steady changes add up.`,
    `**Staying invested 5 more years** adds roughly **${formatInrShort(dLonger)}**. Time in the market tends to matter most.`,
    `**At 6% inflation**, this ${formatInrShort(future)} would buy what **${formatInrShort(realValue)}** buys today — plan for real, not just nominal, wealth.`,
  ];
  if (config.stepUp) {
    ai.push(stepUp
      ? 'Your **10% yearly step-up** is doing a lot of the work here — growing the amount with your income compounds hard.'
      : `**A 10% yearly step-up** could add about **${formatInrShort(dStep)}**, just by raising your SIP as your income grows.`);
  }

  const rows = result.series.filter((p) => p.year >= 1).map((p) => ({
    year: p.year,
    invested: formatInrShort(p.invested),
    wealth: formatInrShort(p.value),
    profit: `+${formatInrShort(Math.max(p.value - p.invested, 0))}`,
    mult: `${p.invested > 0 ? (p.value / p.invested).toFixed(2) : '0.00'}×`,
  }));

  const reset = () => { setVals(initVals()); setStepUp(config.stepUpDefault); };
  const setKey = (k: string, v: number) => setVals((s) => ({ ...s, [k]: v }));

  const subLine = hasMonthly
    ? `From ₹${monthly.toLocaleString('en-IN')}/month over ${years} ${years === 1 ? 'year' : 'years'}`
    : `From a one-time ₹${lumpSum.toLocaleString('en-IN')} over ${years} ${years === 1 ? 'year' : 'years'}`;

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* INPUT PANEL */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Investment</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the sliders — results update instantly.</p>

        {config.inputs.map((inp) => (
          <RangeField
            key={inp.key}
            label={inp.label}
            tip={inp.tip}
            value={vals[inp.key]}
            min={inp.min}
            max={inp.max}
            step={inp.step}
            format={(n) => fmtValue(inp.fmt, n)}
            presets={inp.presets.map((v) => ({ label: fmtPreset(inp.fmt, v), value: v }))}
            onChange={(n) => setKey(inp.key, n)}
          />
        ))}

        {config.stepUp && (
          <div className="mb-3.5">
            <ToggleRow title="Step-up SIP" sub="Increase SIP 10% every year" on={stepUp} onToggle={() => setStepUp((v) => !v)} />
          </div>
        )}

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
          <Kpi hero label="Estimated Future Wealth" value={formatInrShort(future)} sub={subLine} />
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
            {whatIfCards.map((w) => <WhatIfCard key={w.name} {...w} />)}
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
        {related.length > 0 && (
          <Section>
            <SectionHeader index="✦" title="Related Calculators" />
            <div className="flex gap-3 overflow-x-auto pb-1 sm:grid sm:grid-cols-2 sm:overflow-visible lg:grid-cols-4">
              {related.map((c) => (
                <RelatedCard key={c.slug} emoji={c.emoji} name={c.name} desc={c.sub} accent="royal" href={`/calculators/${c.slug}`} />
              ))}
            </div>
          </Section>
        )}

        {/* Sticky calc bar */}
        <div className="fixed bottom-[18px] left-1/2 z-[55] flex -translate-x-1/2 items-center gap-3.5 rounded-2xl bg-navy/95 px-4 py-3 shadow-[0_24px_60px_-20px_rgba(15,23,42,.45)] backdrop-blur">
          <div className="text-white">
            <small className="block text-[10px] font-semibold uppercase tracking-[0.04em] text-slate-400">Future Wealth</small>
            <span className="text-small font-bold">{formatInrShort(future)}</span>
          </div>
          <Btn variant="pri" className="px-3.5">Calculate</Btn>
        </div>
      </div>
    </div>
  );
}

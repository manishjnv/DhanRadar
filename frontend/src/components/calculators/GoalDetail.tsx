'use client';

/**
 * GoalDetail — the config-driven result view for the E2 family (Goal SIP /
 * Savings Goal). Works backward from a target to the monthly SIP (and one-time
 * lump) needed to reach it, via the `solveGoal` engine, and illustrates the plan
 * growing toward the goal with `computeSip`.
 *
 * COMPLIANCE: figures are the USER's own computed numbers (not a DhanRadar fund
 * score). The assumed return / inflation are labelled as the user's assumptions,
 * the disclaimer + What-If sit beside the result, and the AI cards are templated
 * from the user's own inputs (no LLM). No advisory verbs.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, GrowthChart, WhatIfCard, AiCard, RelatedCard, SoWhat } from './ui';
import { solveGoal, computeSip, formatInrShort } from '@/lib/finance';
import { type CalcConfig, getConfig, fmtValue, fmtPreset } from './registry';

export function GoalDetail({ config }: { config: CalcConfig }) {
  const initVals = React.useCallback(() => {
    const o: Record<string, number> = {};
    config.inputs.forEach((inp) => { o[inp.key] = inp.default; });
    return o;
  }, [config]);

  const [vals, setVals] = React.useState<Record<string, number>>(initVals);

  const target = vals.target ?? 0;
  const years = vals.years ?? 0;
  const rate = vals.rate ?? 0;
  const inflation = vals.inflation ?? 0;
  const current = vals.current ?? 0;
  const hasInflation = config.inputs.some((i) => i.key === 'inflation');

  const goalInput = { targetToday: target, years, annualRatePct: rate, inflationPct: inflation, currentSavings: current };
  const result = React.useMemo(
    () => solveGoal({ targetToday: target, years, annualRatePct: rate, inflationPct: inflation, currentSavings: current }),
    [target, years, rate, inflation, current],
  );

  const { requiredMonthly, requiredLump, inflatedTarget } = result;
  const months = Math.round(years * 12);
  const totalInvested = requiredMonthly * months + current;

  // Plan growth toward the goal, for the chart (reaches the inflated target).
  const projection = React.useMemo(
    () => computeSip({ monthlySip: requiredMonthly, lumpSum: current, years, annualRatePct: rate }),
    [requiredMonthly, current, years, rate],
  );

  const monthlyWith = (patch: Partial<typeof goalInput>) => solveGoal({ ...goalInput, ...patch }).requiredMonthly;
  const card = (name: string, val: string, m: number) => {
    const delta = m - requiredMonthly;
    return { name, val, result: `${formatInrShort(m)}/mo`, delta: `${formatInrShort(Math.abs(delta))}/mo ${delta <= 0 ? 'less' : 'more'}`, up: delta <= 0 };
  };

  const whatIf = [
    card('Invest 5 years longer', `${years + 5} yrs`, monthlyWith({ years: years + 5 })),
    card('Earn 2% more', `${rate + 2}%`, monthlyWith({ annualRatePct: rate + 2 })),
    card('Earn 2% less', `${Math.max(rate - 2, 0)}%`, monthlyWith({ annualRatePct: Math.max(rate - 2, 0) })),
  ];
  if (hasInflation) {
    whatIf.push(card('Inflation 2% lower', `${Math.max(inflation - 2, 0)}%`, monthlyWith({ inflationPct: Math.max(inflation - 2, 0) })));
  }
  whatIf.push(card('Bigger goal (+₹10 L)', `${formatInrShort(target + 1000000)}`, monthlyWith({ targetToday: target + 1000000 })));

  const ai = [
    `**Investing 5 more years** drops the monthly SIP to about **${formatInrShort(monthlyWith({ years: years + 5 }))}** — time does most of the heavy lifting.`,
    `At your assumed **${rate}% return**, a one-time **${formatInrShort(requiredLump)}** today would also reach this goal instead of the monthly SIP.`,
  ];
  if (hasInflation && inflation > 0) {
    ai.push(`**${inflation}% inflation** turns today's ${formatInrShort(target)} goal into **${formatInrShort(inflatedTarget)}** by then — that future cost is what you're really saving for.`);
  }

  const reset = () => setVals(initVals());
  const setKey = (k: string, v: number) => setVals((s) => ({ ...s, [k]: v }));
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* INPUT PANEL */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Goal</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the sliders — the monthly SIP updates instantly.</p>

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
          <Kpi hero label="Monthly SIP Needed" value={`${formatInrShort(requiredMonthly)}/mo`} sub={`To reach ${formatInrShort(inflatedTarget)} in ${years} ${years === 1 ? 'year' : 'years'}`} />
          <Kpi label="Goal’s Future Cost" value={formatInrShort(inflatedTarget)} sub={hasInflation && inflation > 0 ? `${inflation}% inflation on ${formatInrShort(target)}` : 'In today’s money'} />
          <Kpi label="Or One-time Today" value={formatInrShort(requiredLump)} sub="Lump sum instead of monthly" />
          <Kpi label="Total You’ll Invest" value={formatInrShort(totalInvested)} sub="Across the whole period" accent="pos" />
        </div>

        {/* Plan growth */}
        <Panel className="mt-3.5">
          <div className="mb-1.5 flex items-center justify-between">
            <div className="text-small font-medium text-ink">Your Plan vs the Goal</div>
            <div className="text-caption tracking-normal text-ink-muted">Invested vs Value</div>
          </div>
          <GrowthChart series={projection.series} />
          <div className="mt-3 flex flex-wrap gap-4">
            <span className="inline-flex items-center gap-1.5 text-caption tracking-normal text-ink-secondary"><span className="h-2.5 w-2.5 rounded-[3px] bg-royal" />Plan Value</span>
            <span className="inline-flex items-center gap-1.5 text-caption tracking-normal text-ink-secondary"><span className="h-2.5 w-2.5 rounded-[3px] bg-surface-3" />Money Invested</span>
          </div>
          <SoWhat>
            Reaching <b className="font-semibold text-ink">{formatInrShort(inflatedTarget)}</b> needs about <b className="font-semibold text-ink">{formatInrShort(requiredMonthly)}/month</b> at your assumed {rate}% return. Returns vary year to year, so treat this as a guide and revisit it.
          </SoWhat>
        </Panel>

        {/* What if */}
        <Section className="mt-[18px]">
          <SectionHeader index="✦" title="What If…" info="What lowers the monthly SIP" />
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
            <DisclosureBundle notAdvice="For education only — not investment advice. These figures illustrate how your own inputs change the saving needed; they are not recommendations to buy, sell, or hold any fund. Estimates assume a constant annual return, which real markets do not provide." />
          </div>
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

        {/* Sticky bar */}
        <div className="fixed bottom-[18px] left-1/2 z-[55] flex -translate-x-1/2 items-center gap-3.5 rounded-2xl bg-navy/95 px-4 py-3 shadow-[0_24px_60px_-20px_rgba(15,23,42,.45)] backdrop-blur">
          <div className="text-white">
            <small className="block text-[10px] font-semibold uppercase tracking-[0.04em] text-slate-400">Monthly SIP</small>
            <span className="text-small font-bold">{formatInrShort(requiredMonthly)}/mo</span>
          </div>
          <Btn variant="pri" className="px-3.5">Calculate</Btn>
        </div>
      </div>
    </div>
  );
}

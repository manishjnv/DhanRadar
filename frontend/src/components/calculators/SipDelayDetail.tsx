'use client';

/**
 * SipDelayDetail — 'sip-delay' view (E6): shows how waiting before starting a
 * SIP erodes your final corpus — both sides run to the SAME end date, so delay
 * means fewer months invested, not fewer years from today.
 *
 * COMPLIANCE: educational estimate only. The return is the USER's own assumption,
 * not a DhanRadar prediction. No advisory verbs; no numeric fund scores in DOM.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, WhatIfCard, AiCard, RelatedCard, SoWhat } from './ui';
import { computeSip, formatInr, formatInrShort } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

/** Format months as "2y 0m", "1y 6m", "0y 6m", etc. */
function fmtMonths(n: number): string {
  const y = Math.floor(n / 12);
  const m = n % 12;
  return `${y}y ${m}m`;
}

export function SipDelayDetail({ config }: { config: CalcConfig }) {
  const [monthly, setMonthly] = React.useState(25000);
  const [rate, setRate] = React.useState(12);
  const [horizon, setHorizon] = React.useState(15);
  const [delay, setDelay] = React.useState(12);
  const resultRef = React.useRef<HTMLDivElement>(null);

  // Core compute — same END date: delaying means fewer years invested.
  const startNow = React.useMemo(
    () => computeSip({ monthlySip: monthly, lumpSum: 0, years: horizon, annualRatePct: rate }).futureValue,
    [monthly, rate, horizon],
  );

  const delayedFV = React.useMemo(() => {
    const delayedYears = Math.max(horizon - delay / 12, 0);
    return computeSip({ monthlySip: monthly, lumpSum: 0, years: delayedYears, annualRatePct: rate }).futureValue;
  }, [monthly, rate, horizon, delay]);

  const costOfDelay = Math.max(startNow - delayedFV, 0);

  const fvAtDelay = (d: number): number => {
    const dy = Math.max(horizon - d / 12, 0);
    return computeSip({ monthlySip: monthly, lumpSum: 0, years: dy, annualRatePct: rate }).futureValue;
  };

  // What-if cards — fixed delay scenarios.
  const whatIfDelays: { months: number; label: string }[] = [
    { months: 6, label: 'Wait 6 months' },
    { months: 12, label: 'Wait 1 year' },
    { months: 24, label: 'Wait 2 years' },
    { months: 60, label: 'Wait 5 years' },
  ];
  const whatIfCards = whatIfDelays.map(({ months, label }) => {
    const fv = fvAtDelay(months);
    const cost = Math.max(startNow - fv, 0);
    return {
      name: label,
      val: fmtMonths(months),
      result: formatInrShort(fv),
      delta: `${formatInrShort(cost)} less`,
      up: false,
    };
  });

  const reset = () => { setMonthly(25000); setRate(12); setHorizon(15); setDelay(12); };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — ₹${monthly.toLocaleString('en-IN')}/mo for ${horizon} yrs at ${rate}% (your assumption). Start now: ${formatInr(startNow)}. Wait ${fmtMonths(delay)}: ${formatInr(delayedFV)}. Cost of waiting: ${formatInr(costOfDelay)}.`,
    note: 'Educational illustration only — not investment advice. The return rate is your own assumption; real markets do not provide a constant return. Mutual fund investments are subject to market risk.',
    headers: ['Scenario', 'Years Invested', 'Estimated Corpus', 'Cost of Waiting'],
    rows: [
      ['Start immediately', `${horizon} yrs`, Math.round(startNow), 0],
      ...whatIfDelays.map(({ months, label }) => {
        const fv = fvAtDelay(months);
        return [label, `${(horizon - months / 12).toFixed(1)} yrs`, Math.round(fv), Math.round(Math.max(startNow - fv, 0))];
      }),
    ],
    colFormats: ['text', 'text', 'inr', 'inr'],
  };

  const aiInsights = [
    `**Starting now vs waiting ${fmtMonths(delay)}** costs an estimated **${formatInrShort(costOfDelay)}** — that's the compounding lost on ${fmtMonths(delay)} of missing contributions and growth.`,
    `**Time in the market matters more than timing it.** Even a ₹${monthly.toLocaleString('en-IN')}/month SIP at your chosen ${rate}% grows to ${formatInrShort(startNow)} over ${horizon} years. Waiting chips that number down for every month you delay.`,
  ];

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* INPUT PANEL */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your SIP Plan</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the sliders — see how delay shrinks your corpus.</p>

        <RangeField
          label="Monthly SIP"
          tip="What you'd invest each month"
          value={monthly}
          min={500}
          max={200000}
          step={500}
          format={formatInr}
          presets={[
            { label: '₹5K', value: 5000 },
            { label: '₹10K', value: 10000 },
            { label: '₹25K', value: 25000 },
            { label: '₹50K', value: 50000 },
          ]}
          onChange={setMonthly}
          unit="₹"
        />

        <RangeField
          label="Assumed Return"
          tip="A return you choose, not our prediction"
          value={rate}
          min={1}
          max={30}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[
            { label: '8%', value: 8 },
            { label: '10%', value: 10 },
            { label: '12%', value: 12 },
            { label: '15%', value: 15 },
          ]}
          onChange={setRate}
          unit="%"
        />

        <RangeField
          label="Target Horizon"
          tip="Years from today until you need the money"
          value={horizon}
          min={2}
          max={40}
          step={1}
          format={(n) => `${n} yrs`}
          presets={[
            { label: '10y', value: 10 },
            { label: '15y', value: 15 },
            { label: '20y', value: 20 },
            { label: '30y', value: 30 },
          ]}
          onChange={setHorizon}
          unit="yrs"
        />

        <RangeField
          label="Delay"
          tip="How long you wait before starting"
          value={delay}
          min={0}
          max={60}
          step={1}
          format={fmtMonths}
          presets={[
            { label: '6m', value: 6 },
            { label: '1y', value: 12 },
            { label: '2y', value: 24 },
            { label: '5y', value: 60 },
          ]}
          onChange={setDelay}
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      {/* RESULT PANEL */}
      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            hero
            label="Cost of Waiting"
            value={formatInr(costOfDelay)}
            sub={`Waiting ${fmtMonths(delay)}`}
          />
          <Kpi
            label="If You Start Now"
            value={formatInr(startNow)}
            sub={`${horizon} yrs at ${rate}% (your assumption)`}
            accent="pos"
          />
          <Kpi
            label="If You Wait"
            value={formatInr(delayedFV)}
            sub={`${Math.max(horizon - delay / 12, 0).toFixed(1)} yrs invested`}
          />
          <Kpi
            label="Months Delayed"
            value={`${delay} mo`}
            sub={fmtMonths(delay)}
          />
        </div>

        {/* What If section */}
        <Section className="mt-3.5">
          <SectionHeader index="✦" title="What If…" info="Cost at different delay lengths" />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {whatIfCards.map((w) => (
              <WhatIfCard key={w.name} {...w} />
            ))}
          </div>
          <Panel className="mt-3">
            <SoWhat>
              All four scenarios assume the same end date ({horizon} years from today) — so waiting simply means <b className="font-semibold text-ink">fewer months invested</b>, not more time ahead. The earlier you begin, the more compounding works in your favour.
            </SoWhat>
          </Panel>
        </Section>

        {/* AI Insights */}
        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {aiInsights.map((t, i) => (
              <AiCard key={i} text={t} />
            ))}
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. The return is your own assumption; real markets vary. Mutual fund investments are subject to market risk." />
          </div>
        </Section>

        {/* Related Calculators */}
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
      </div>
    </div>
  );
}

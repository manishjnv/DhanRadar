'use client';

/**
 * DirectVsRegularDetail — 'direct-vs-regular' Versus view (§12).
 *
 * Compares a Direct plan vs Regular plan for the SAME underlying portfolio.
 * The only difference is the expense ratio — Regular includes a distributor
 * commission. The gap compounds over time into a meaningful difference.
 *
 * COMPLIANCE: factual on the user's own numbers; no advisory verbs; winner
 * label says "for your inputs" only; does not tell users to switch plans.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, RangeField, AiCard, RelatedCard } from './ui';
import { computeSip, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { VersusLayout, type VsOption } from './VersusLayout';
import { ResultActions, type ExcelTable } from './actions';

export function DirectVsRegularDetail({ config }: { config: CalcConfig }) {
  const [sip, setSip] = React.useState(25000);
  const [gross, setGross] = React.useState(12);
  const [years, setYears] = React.useState(15);
  const [directER, setDirectER] = React.useState(0.5);
  const [regularER, setRegularER] = React.useState(1.5);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const { directFv, regularFv, invested, gap } = React.useMemo(() => {
    const dFv = computeSip({ monthlySip: sip, lumpSum: 0, years, annualRatePct: Math.max(gross - directER, 0) }).futureValue;
    const rFv = computeSip({ monthlySip: sip, lumpSum: 0, years, annualRatePct: Math.max(gross - regularER, 0) }).futureValue;
    return {
      directFv: dFv,
      regularFv: rFv,
      invested: sip * years * 12,
      gap: dFv - rFv,
    };
  }, [sip, gross, years, directER, regularER]);

  const directWins = directFv >= regularFv;
  const erDiff = (regularER - directER).toFixed(2);
  const absDiff = formatInr(Math.abs(gap));

  const options: VsOption[] = [
    {
      label: 'Direct Plan',
      headline: formatInr(directFv),
      headlineLabel: 'Value at the end',
      winner: directWins,
      rows: [
        { label: 'Net return', value: `${Math.max(gross - directER, 0).toFixed(2)}%` },
        { label: 'Invested', value: formatInr(invested) },
        { label: 'Gain', value: formatInr(directFv - invested) },
      ],
    },
    {
      label: 'Regular Plan',
      headline: formatInr(regularFv),
      headlineLabel: 'Value at the end',
      winner: !directWins,
      rows: [
        { label: 'Net return', value: `${Math.max(gross - regularER, 0).toFixed(2)}%` },
        { label: 'Invested', value: formatInr(invested) },
        { label: 'Gain', value: formatInr(regularFv - invested) },
      ],
    },
  ];

  const verdict = (
    <>
      A <strong className="font-semibold text-ink">{erDiff}%</strong> lower yearly expense ratio compounds into about{' '}
      <strong className="font-semibold text-ink">{absDiff}</strong>{' '}
      {gap >= 0 ? 'more' : 'less'} over {years} {years === 1 ? 'yr' : 'yrs'} &mdash; the SAME fund, just the cheaper plan. Factual on your inputs.
    </>
  );

  const caveats = [
    'Direct and Regular are the SAME underlying portfolio — the Regular plan’s expense ratio includes a distributor commission.',
    'A Direct plan means you pick and review funds yourself; a Regular plan comes with an advisor or distributor whose guidance has value to some investors.',
    'Expense ratios change over time and differ by fund — use the actual ratios from the scheme document.',
  ];

  const excelTable: ExcelTable = {
    summary: `${config.name} — ₹${sip.toLocaleString('en-IN')}/mo SIP at ${gross}% gross for ${years} yrs: Direct ${formatInr(directFv)}, Regular ${formatInr(regularFv)}, difference ${formatInr(Math.abs(gap))}.`,
    note: 'Educational illustration only — not investment advice. Returns are the user’s own assumption; real market returns vary. Expense ratios differ by fund and change over time.',
    headers: ['Plan', 'Final Value'],
    rows: [
      ['Direct final', Math.round(directFv)],
      ['Regular final', Math.round(regularFv)],
      ['Difference', Math.round(gap)],
    ],
    colFormats: ['text', 'inr'],
  };

  const reset = () => { setSip(25000); setGross(12); setYears(15); setDirectER(0.5); setRegularER(1.5); };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Numbers</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          Same fund, same gross return &mdash; only the expense ratio differs.
        </p>

        <RangeField
          label="Monthly SIP"
          tip="What you invest each month"
          value={sip}
          min={500}
          max={1000000}
          step={500}
          format={formatInr}
          presets={[
            { label: '₹10K', value: 10000 },
            { label: '₹25K', value: 25000 },
            { label: '₹50K', value: 50000 },
            { label: '₹1L', value: 100000 },
          ]}
          onChange={setSip}
          unit="₹"
        />

        <RangeField
          label="Gross Return"
          tip="Before fund expenses — your assumption"
          value={gross}
          min={1}
          max={30}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[
            { label: '10%', value: 10 },
            { label: '12%', value: 12 },
            { label: '15%', value: 15 },
          ]}
          onChange={setGross}
          unit="%"
        />

        <RangeField
          label="Years"
          tip="How long you stay invested"
          value={years}
          min={1}
          max={40}
          step={1}
          format={(n) => `${n} ${n === 1 ? 'yr' : 'yrs'}`}
          presets={[
            { label: '10 yrs', value: 10 },
            { label: '15 yrs', value: 15 },
            { label: '20 yrs', value: 20 },
            { label: '25 yrs', value: 25 },
          ]}
          onChange={setYears}
          unit="yrs"
        />

        <RangeField
          label="Direct Expense Ratio"
          tip="Annual cost of the Direct plan"
          value={directER}
          min={0}
          max={2.5}
          step={0.05}
          format={(n) => `${n.toFixed(2)}%`}
          presets={[
            { label: '0.25%', value: 0.25 },
            { label: '0.5%', value: 0.5 },
            { label: '1%', value: 1 },
          ]}
          onChange={setDirectER}
          unit="%"
        />

        <RangeField
          label="Regular Expense Ratio"
          tip="Annual cost of the Regular plan"
          value={regularER}
          min={0}
          max={2.5}
          step={0.05}
          format={(n) => `${n.toFixed(2)}%`}
          presets={[
            { label: '1%', value: 1 },
            { label: '1.5%', value: 1.5 },
            { label: '2%', value: 2 },
          ]}
          onChange={setRegularER}
          unit="%"
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <VersusLayout options={options} verdict={verdict} caveats={caveats} />

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text="**A small yearly cost gap compounds silently.** Even 1% extra in expenses each year doesn’t feel large, but over 15–20 years it quietly erodes a significant slice of your corpus — because the fee is charged on the growing balance, not just what you put in." />
            <AiCard text="**The expense ratio works like a guaranteed drag.** Markets go up and down, but the fund house deducts its expense ratio every single year regardless. That makes a lower ratio the one near-certain edge available to you within the same fund." />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. A cost illustration on your own inputs; returns are your assumption and real markets vary." />
          </div>
        </Section>

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

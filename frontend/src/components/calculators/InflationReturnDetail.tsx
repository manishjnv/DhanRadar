'use client';

/**
 * InflationReturnDetail — 'inflation-return' view (E6): shows the real
 * (inflation-adjusted) annual return and what a sample lump sum is worth in
 * today's money after the nominal growth and inflation are applied.
 *
 * COMPLIANCE: an educational ESTIMATE on the user's own assumptions — not
 * investment advice. Returns and inflation are the user's own numbers.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { realReturn, } from '@/lib/finance/returns';
import { computeSip, formatInr } from '@/lib/finance/accumulation';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

export function InflationReturnDetail({ config }: { config: CalcConfig }) {
  const [nominal, setNominal] = React.useState(12);
  const [inflation, setInflation] = React.useState(6);
  const [sample, setSample] = React.useState(100000);
  const [years, setYears] = React.useState(15);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const { realPct, nominalFv, realFv } = React.useMemo(() => {
    const rPct = realReturn(nominal, inflation);
    const nFv = computeSip({ monthlySip: 0, lumpSum: sample, years, annualRatePct: nominal }).futureValue;
    const rFv = nFv / Math.pow(1 + inflation / 100, years);
    return { realPct: rPct, nominalFv: nFv, realFv: rFv };
  }, [nominal, inflation, sample, years]);

  const reset = () => { setNominal(12); setInflation(6); setSample(100000); setYears(15); };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${nominal}% nominal, ${inflation}% inflation → ${realPct.toFixed(2)}% real return; ${formatInr(sample)} grows to ${formatInr(nominalFv)} nominal (${formatInr(realFv)} in today's money) over ${years} years.`,
    note: `Educational estimate only — not investment advice. Returns and inflation are your own assumptions; real markets vary. Nominal FV uses annual compounding on a lump sum.`,
    headers: ['Item', 'Value'],
    rows: [
      ['Nominal return (your assumption)', `${nominal}%`],
      ['Inflation (your assumption)', `${inflation}%`],
      ['Real return', `${realPct.toFixed(2)}%`],
      ['Sample amount', Math.round(sample)],
      ['Nominal future value', Math.round(nominalFv)],
      ['Real value (today\'s money)', Math.round(realFv)],
      ['Duration (years)', years],
    ],
    colFormats: ['text', 'text'],
  };

  const row = (label: string, value: string, strong?: boolean) => (
    <div className="flex items-center justify-between border-b border-line py-2 last:border-b-0">
      <span className="text-small text-ink-secondary">{label}</span>
      <span className={`font-mono text-small ${strong ? 'font-bold text-ink' : 'font-semibold text-ink-secondary'}`}>{value}</span>
    </div>
  );

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Assumptions</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Enter your own expected return and inflation to see what your money earns in real terms.</p>

        <RangeField
          label="Nominal Return"
          tip="The headline return before inflation"
          value={nominal}
          min={1}
          max={30}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[{ label: '8%', value: 8 }, { label: '10%', value: 10 }, { label: '12%', value: 12 }, { label: '15%', value: 15 }]}
          onChange={setNominal}
          unit="%"
        />
        <RangeField
          label="Inflation"
          tip="How fast prices rise each year"
          value={inflation}
          min={0}
          max={12}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[{ label: '4%', value: 4 }, { label: '6%', value: 6 }, { label: '8%', value: 8 }]}
          onChange={setInflation}
          unit="%"
        />
        <RangeField
          label="Sample Amount"
          tip="An amount to show its real future worth"
          value={sample}
          min={1000}
          max={100000000}
          step={1000}
          format={formatInr}
          presets={[{ label: '₹50K', value: 50000 }, { label: '₹1L', value: 100000 }, { label: '₹5L', value: 500000 }, { label: '₹10L', value: 1000000 }]}
          onChange={setSample}
          unit="₹"
        />
        <RangeField
          label="Years"
          tip="Over how many years"
          value={years}
          min={1}
          max={40}
          step={1}
          format={(n) => `${n} yrs`}
          presets={[{ label: '5', value: 5 }, { label: '10', value: 10 }, { label: '15', value: 15 }, { label: '20', value: 20 }]}
          onChange={setYears}
          unit="yrs"
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{ nominal, inflation, sample, years }} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi hero label="Real Return" value={`${realPct.toFixed(2)}%`} sub="After inflation" />
          <Kpi label="Nominal Return" value={`${nominal}%`} sub="Your assumption" />
          <Kpi label="Inflation" value={`${inflation}%`} sub="Your assumption" />
          <Kpi label="Real Value of Sample" value={formatInr(realFv)} sub={`${formatInr(nominalFv)} nominal`} accent="pos" />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Breakdown" />
          <Panel>
            {row('Nominal return (your assumption)', `${nominal}%`)}
            {row('Inflation (your assumption)', `${inflation}%`)}
            {row('Real return', `${realPct.toFixed(2)}%`, true)}
            {row(`${formatInr(sample)} grows to (nominal)`, formatInr(nominalFv))}
            {row('Real value in today\'s money', formatInr(realFv), true)}
            <SoWhat>
              Real return is what your money earns <b className="font-semibold text-ink">above</b> rising prices. At {nominal}% nominal and {inflation}% inflation, you keep only {realPct.toFixed(2)}% in real terms. That {formatInr(nominalFv)} nominal sum buys only {formatInr(realFv)} worth of goods at today's prices — inflation quietly erodes the rest.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={`**Real return is what matters for your standard of living.** A ${nominal}% headline return sounds strong, but with ${inflation}% inflation your purchasing power grows at only ${realPct.toFixed(2)}% per year — compounding makes that gap large over ${years} years.`} />
            <AiCard text={`**Inflation is the silent fee on your savings.** Your ${formatInr(sample)} grows to ${formatInr(nominalFv)} nominally, but that future sum buys only ${formatInr(realFv)} of today's goods. These are your own assumed figures — actual outcomes depend on the investments you choose.`} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. Returns and inflation are your own assumptions; real markets vary." />
          </div>
        </Section>

        {related.length > 0 && (
          <Section>
            <SectionHeader index="✦" title="Related Calculators" />
            <div className="flex gap-3 overflow-x-auto pb-1 sm:grid sm:grid-cols-2 sm:overflow-visible lg:grid-cols-4">
              {related.map((c) => <RelatedCard key={c.slug} emoji={c.emoji} name={c.name} desc={c.sub} accent="royal" href={`/calculators/${c.slug}`} />)}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

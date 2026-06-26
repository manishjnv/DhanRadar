'use client';

/**
 * TermCoverDetail — 'term-cover' view (E10): a needs-based gap analysis that
 * estimates how much term life cover an earner might need to let their family
 * replace income, clear outstanding loans, and fund future goals.
 *
 * COMPLIANCE: INDICATIVE figure only — not insurance advice, not a product
 * pick, not a recommendation to buy any policy. The discount rate is the
 * user's own assumption. No insurer or policy is named anywhere.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeTermCover, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

export function TermCoverDetail({ config }: { config: CalcConfig }) {
  const [annualIncome, setAnnualIncome] = React.useState(1200000);
  const [yearsToCover, setYearsToCover] = React.useState(20);
  const [discountRatePct, setDiscountRatePct] = React.useState(4);
  const [outstandingLoans, setOutstandingLoans] = React.useState(3000000);
  const [futureGoals, setFutureGoals] = React.useState(2000000);
  const [existingCoverAssets, setExistingCoverAssets] = React.useState(500000);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(
    () =>
      computeTermCover({
        annualIncome,
        yearsToCover,
        discountRatePct,
        outstandingLoans,
        futureGoals,
        existingCoverAssets,
      }),
    [annualIncome, yearsToCover, discountRatePct, outstandingLoans, futureGoals, existingCoverAssets],
  );

  const reset = () => {
    setAnnualIncome(1200000);
    setYearsToCover(20);
    setDiscountRatePct(4);
    setOutstandingLoans(3000000);
    setFutureGoals(2000000);
    setExistingCoverAssets(500000);
  };

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — indicative gap ${formatInr(r.gap)}; income replacement PV ${formatInr(r.incomeReplacement)}, loans ${formatInr(outstandingLoans)}, goals ${formatInr(futureGoals)}, total need ${formatInr(r.totalNeed)}, existing cover ${formatInr(existingCoverAssets)}.`,
    note: 'Indicative estimate only — not insurance advice or a product recommendation. Based on your own inputs; the discount rate is your assumption. Discuss your actual cover requirement with a licensed insurance advisor.',
    headers: ['Item', 'Amount'],
    rows: [
      ['Income replacement (PV)', Math.round(r.incomeReplacement)],
      ['+ Outstanding loans', Math.round(outstandingLoans)],
      ['+ Future goals', Math.round(futureGoals)],
      ['= Total need', Math.round(r.totalNeed)],
      ['− Existing cover & assets', Math.round(existingCoverAssets)],
      ['= Indicative gap', Math.round(r.gap)],
    ],
    colFormats: ['text', 'inr'],
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
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Situation</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          Enter your figures to get an indicative term cover gap. Discuss the actual amount with a licensed advisor.
        </p>

        <RangeField
          label="Annual Income"
          tip="What you earn in a year today"
          value={annualIncome}
          min={100000}
          max={100000000}
          step={50000}
          format={formatInr}
          presets={[
            { label: '₹6L', value: 600000 },
            { label: '₹12L', value: 1200000 },
            { label: '₹25L', value: 2500000 },
          ]}
          onChange={setAnnualIncome}
          unit="₹"
        />
        <RangeField
          label="Years to Replace"
          tip="How many years your family needs the income"
          value={yearsToCover}
          min={1}
          max={40}
          step={1}
          format={(n) => `${n} ${n === 1 ? 'yr' : 'yrs'}`}
          presets={[
            { label: '10', value: 10 },
            { label: '15', value: 15 },
            { label: '20', value: 20 },
            { label: '25', value: 25 },
          ]}
          onChange={setYearsToCover}
          unit="yrs"
        />
        <RangeField
          label="Net Discount Rate"
          tip="Return minus income growth — your assumption"
          value={discountRatePct}
          min={0}
          max={12}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[
            { label: '2%', value: 2 },
            { label: '4%', value: 4 },
            { label: '6%', value: 6 },
          ]}
          onChange={setDiscountRatePct}
          unit="%"
        />
        <RangeField
          label="Outstanding Loans"
          tip="Home/car/personal loans to clear"
          value={outstandingLoans}
          min={0}
          max={100000000}
          step={100000}
          format={formatInr}
          presets={[
            { label: '₹0', value: 0 },
            { label: '₹25L', value: 2500000 },
            { label: '₹50L', value: 5000000 },
            { label: '₹1Cr', value: 10000000 },
          ]}
          onChange={setOutstandingLoans}
          unit="₹"
        />
        <RangeField
          label="Future Goals"
          tip="Big goals to fund (education, marriage…)"
          value={futureGoals}
          min={0}
          max={100000000}
          step={100000}
          format={formatInr}
          presets={[
            { label: '₹0', value: 0 },
            { label: '₹20L', value: 2000000 },
            { label: '₹50L', value: 5000000 },
          ]}
          onChange={setFutureGoals}
          unit="₹"
        />
        <RangeField
          label="Existing Cover & Assets"
          tip="Existing life cover + liquid savings"
          value={existingCoverAssets}
          min={0}
          max={1000000000}
          step={100000}
          format={formatInr}
          presets={[
            { label: '₹0', value: 0 },
            { label: '₹50L', value: 5000000 },
            { label: '₹1Cr', value: 10000000 },
          ]}
          onChange={setExistingCoverAssets}
          unit="₹"
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi
            hero
            label="Cover Gap"
            value={formatInr(r.gap)}
            sub="Indicative — discuss with an advisor"
          />
          <Kpi
            label="Income Replacement"
            value={formatInr(r.incomeReplacement)}
            sub={`${yearsToCover} ${yearsToCover === 1 ? 'yr' : 'yrs'} of income, today's value`}
          />
          <Kpi
            label="Total Need"
            value={formatInr(r.totalNeed)}
            sub="Income + loans + goals"
          />
          <Kpi
            label="Already Covered"
            value={formatInr(existingCoverAssets)}
            sub="Existing cover & liquid assets"
            accent="pos"
          />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Needs Breakdown" />
          <Panel>
            {row('Income replacement (PV)', formatInr(r.incomeReplacement))}
            {row('+ Outstanding loans', `+ ${formatInr(outstandingLoans)}`)}
            {row('+ Future goals', `+ ${formatInr(futureGoals)}`)}
            {row('= Total need', formatInr(r.totalNeed), true)}
            {row('− Existing cover & assets', `− ${formatInr(existingCoverAssets)}`)}
            {row('= Indicative gap', formatInr(r.gap), true)}
            <SoWhat>
              A term plan sized to roughly meet this gap lets your family <b className="font-semibold text-ink">replace {yearsToCover} {yearsToCover === 1 ? 'yr' : 'yrs'} of income</b>, clear outstanding debts, and fund the goals you have listed — all on your own figures. This is an indicative starting point; the right amount depends on your full financial picture.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text="**The income replacement piece** is the present value of your annual income over the chosen years, discounted at your assumed net rate. A lower discount rate gives a higher (more conservative) figure — both are valid assumptions; the choice is yours." />
            <AiCard text="**Loans and goals are added at face value** because they need to be met in full regardless of when they fall due. Subtracting existing cover and liquid assets from the total gives the indicative shortfall your term plan could aim to bridge." />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not insurance advice or a product recommendation. An indicative figure on your own inputs; discuss your actual cover with a licensed insurance advisor." />
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

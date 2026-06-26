'use client';

/**
 * HlvDetail — 'hlv' view (E10): Human Life Value (income-replacement).
 *
 * COMPLIANCE: an INDICATIVE estimate on the user's own figures only — not
 * insurance advice, not a product recommendation, and not a suggestion to
 * buy any policy. The discount rate is the user's own assumption. No
 * insurer or policy is named. Figures are for education only; discuss
 * your actual cover with a licensed insurance advisor.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeHlv, INSURANCE_CONFIG, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

export function HlvDetail({ config }: { config: CalcConfig }) {
  const [annualIncome, setAnnualIncome] = React.useState(1200000);
  const [currentAge, setCurrentAge] = React.useState(35);
  const [retirementAge, setRetirementAge] = React.useState(60);
  const [discountRatePct, setDiscountRatePct] = React.useState(4);
  const [existingCover, setExistingCover] = React.useState(0);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(
    () => computeHlv({ annualIncome, currentAge, retirementAge, discountRatePct, existingCover }),
    [annualIncome, currentAge, retirementAge, discountRatePct, existingCover],
  );

  const reset = () => {
    setAnnualIncome(1200000);
    setCurrentAge(35);
    setRetirementAge(60);
    setDiscountRatePct(4);
    setExistingCover(0);
  };

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${formatInr(annualIncome)}/yr income, age ${currentAge}→${retirementAge}, ${discountRatePct}% net discount: indicative HLV ${formatInr(r.hlv)}, existing cover ${formatInr(existingCover)}, indicative gap ${formatInr(r.coverGap)}.`,
    note: `Indicative estimate only — not insurance advice or a product recommendation. For education; discuss your actual cover with a licensed insurance advisor. Rule-of-thumb ${INSURANCE_CONFIG.hlvIncomeMultiplier}× check is a simple cross-reference only. ${INSURANCE_CONFIG.asOf} assumptions.`,
    headers: ['Item', 'Amount'],
    rows: [
      ['Annual income', Math.round(annualIncome)],
      ['Working years left', r.workingYears],
      [`Net discount rate (your assumption)`, discountRatePct],
      ['Indicative Human Life Value', Math.round(r.hlv)],
      ['Existing life cover', Math.round(existingCover)],
      [`Indicative gap`, Math.round(r.coverGap)],
      [`Rule-of-thumb check (${INSURANCE_CONFIG.hlvIncomeMultiplier}× income)`, Math.round(r.multiplierCheck)],
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
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Details</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          An indicative income-replacement figure — for education, not advice. Discuss your actual cover needs with a licensed advisor.
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
            { label: '₹50L', value: 5000000 },
          ]}
          onChange={setAnnualIncome}
          unit="₹"
        />
        <RangeField
          label="Current Age"
          tip="Your age today"
          value={currentAge}
          min={18}
          max={65}
          step={1}
          format={(n) => `${n}`}
          presets={[
            { label: '30', value: 30 },
            { label: '35', value: 35 },
            { label: '40', value: 40 },
            { label: '45', value: 45 },
          ]}
          onChange={setCurrentAge}
        />
        <RangeField
          label="Retirement Age"
          tip="When your income stops"
          value={retirementAge}
          min={45}
          max={75}
          step={1}
          format={(n) => `${n}`}
          presets={[
            { label: '55', value: 55 },
            { label: '60', value: 60 },
            { label: '65', value: 65 },
          ]}
          onChange={setRetirementAge}
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
          label="Existing Life Cover"
          tip="Life insurance you already have"
          value={existingCover}
          min={0}
          max={1000000000}
          step={100000}
          format={formatInr}
          presets={[
            { label: '₹0', value: 0 },
            { label: '₹50L', value: 5000000 },
            { label: '₹1Cr', value: 10000000 },
            { label: '₹2Cr', value: 20000000 },
          ]}
          onChange={setExistingCover}
          unit="₹"
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            hero
            label="Human Life Value"
            value={formatInr(r.hlv)}
            sub={`Income replaced over ${r.workingYears} working yrs`}
          />
          <Kpi
            label="Indicative Cover Gap"
            value={formatInr(r.coverGap)}
            sub="After your existing cover"
            accent="pos"
          />
          <Kpi
            label={`Rule-of-Thumb (${INSURANCE_CONFIG.hlvIncomeMultiplier}×)`}
            value={formatInr(r.multiplierCheck)}
            sub="A simple cross-check"
          />
          <Kpi
            label="Working Years Left"
            value={`${r.workingYears} yrs`}
            sub={`Age ${currentAge} → ${retirementAge}`}
          />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="How the Indicative Figure is Built" />
          <Panel>
            {row('Annual income', formatInr(annualIncome))}
            {row('Working years left', `${r.workingYears} yrs`)}
            {row('Net discount rate (your assumption)', `${discountRatePct}%`)}
            {row('Present value of income (HLV)', formatInr(r.hlv), true)}
            {row('Existing life cover', formatInr(existingCover))}
            {row('Indicative gap', formatInr(r.coverGap), true)}
            <SoWhat>
              The <b className="font-semibold text-ink">Human Life Value</b> is the present value of the income a family would lose if the earner were not there — discounted at your assumed <b className="font-semibold text-ink">{discountRatePct}% net rate</b> over <b className="font-semibold text-ink">{r.workingYears} years</b>. The indicative gap is what your existing cover does not yet meet. This is an estimate on your own inputs; actual insurance needs depend on many factors a licensed advisor can assess.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard
              text={`**HLV is the present value of your future income.** At a ${discountRatePct}% net discount rate over ${r.workingYears} years, ₹${(annualIncome / 100000).toFixed(1)} L/yr today works out to an indicative ${formatInr(r.hlv)}. A lower net discount rate raises the figure; a higher one reduces it — adjust the slider to see the effect of your own assumption.`}
            />
            <AiCard
              text={`**The ${INSURANCE_CONFIG.hlvIncomeMultiplier}× income rule of thumb** gives ${formatInr(r.multiplierCheck)} — a quick sanity cross-check. The HLV method accounts for your actual working horizon and a discount rate, so it adapts to your age and income growth expectations rather than applying a fixed multiple.`}
            />
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

'use client';

/**
 * RegimeDetail — &#39;regime&#39; versus view (§12): Old vs New income-tax regime,
 * FY 2025-26. Educational estimate on the user&#39;s own figures — not tax advice.
 *
 * COMPLIANCE: factual on user&#39;s numbers; labels which option is lower for their
 * inputs; no advisory verbs (buy/sell/hold/switch/avoid/caution).
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, RangeField, AiCard, RelatedCard } from './ui';
import { computeRegimeTax, REGIME_CONFIG, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';
import { VersusLayout, type VsOption } from './VersusLayout';

export function RegimeDetail({ config }: { config: CalcConfig }) {
  const [grossIncome, setGrossIncome] = React.useState(1500000);
  const [deductions, setDeductions] = React.useState(250000);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(
    () => computeRegimeTax({ grossIncome, deductions }),
    [grossIncome, deductions],
  );

  const reset = () => { setGrossIncome(1500000); setDeductions(250000); };

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const effRate = (tax: number) =>
    grossIncome > 0 ? `${((tax / grossIncome) * 100).toFixed(1)}%` : '0%';

  const options: VsOption[] = [
    {
      label: 'Old Regime',
      headline: formatInr(r.oldTax),
      headlineLabel: 'Total tax (incl. cess)',
      winner: r.cheaper === 'old',
      rows: [
        { label: 'Taxable income', value: formatInr(r.oldTaxable) },
        { label: 'Deductions used', value: formatInr(deductions) },
        { label: 'Effective rate', value: effRate(r.oldTax) },
      ],
    },
    {
      label: 'New Regime',
      headline: formatInr(r.newTax),
      headlineLabel: 'Total tax (incl. cess)',
      winner: r.cheaper === 'new',
      rows: [
        { label: 'Taxable income', value: formatInr(r.newTaxable) },
        { label: 'Deductions used', value: 'Standard only' },
        { label: 'Effective rate', value: effRate(r.newTax) },
      ],
    },
  ];

  const verdictText =
    r.cheaper === 'equal'
      ? 'For your income and deductions, the two regimes cost the same.'
      : `For your income and deductions, the ${r.cheaper} regime costs ${formatInr(r.saving)} less.`;

  const verdict = (
    <>
      {verdictText} The new regime is the default from FY 2024-25; the old usually wins only
      when your deductions are large. Based on your numbers &mdash; not tax advice.
    </>
  );

  const caveats = [
    'The new regime has lower rates but almost no deductions; the old has higher rates but allows 80C, 80D, HRA, home-loan interest and more.',
    'This models salaried income with the standard deduction and a single deductions total — it ignores surcharge, special-rate income (capital gains), and marginal relief at the rebate edge.',
    `Income up to ₹12 L is effectively tax-free under the new regime (₹5 L under the old) via the 87A rebate.`,
  ];

  const excelTable: ExcelTable = {
    summary: `${config.name} — gross income ${formatInr(grossIncome)}, deductions ${formatInr(deductions)}: old-regime tax ${formatInr(r.oldTax)}, new-regime tax ${formatInr(r.newTax)}, saving ${formatInr(r.saving)} with the ${r.cheaper === 'equal' ? 'either' : r.cheaper} regime.`,
    note: `Educational estimate only — not tax advice. ${REGIME_CONFIG.asOf} rates; surcharge and special-rate incomes are not modelled.`,
    headers: ['Item', 'Amount'],
    rows: [
      ['Old regime tax', r.oldTax],
      ['New regime tax', r.newTax],
      ['Saving with cheaper', r.saving],
    ],
    colFormats: ['text', 'inr'],
  };

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Income &amp; Deductions</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          Enter your gross salary and the deductions you claim under the old regime to see which
          tax option is lower for your numbers.
        </p>

        <RangeField
          label="Gross Annual Income"
          tip="Your total salary income for the year"
          value={grossIncome}
          min={300000}
          max={50000000}
          step={50000}
          format={formatInr}
          presets={[
            { label: '₹10L', value: 1000000 },
            { label: '₹15L', value: 1500000 },
            { label: '₹25L', value: 2500000 },
            { label: '₹50L', value: 5000000 },
          ]}
          onChange={setGrossIncome}
          unit="₹"
        />

        <RangeField
          label="Deductions (Old Regime)"
          tip="80C + 80D + HRA + home-loan interest, etc."
          value={deductions}
          min={0}
          max={5000000}
          step={25000}
          format={formatInr}
          presets={[
            { label: '₹0', value: 0 },
            { label: '₹1.5L', value: 150000 },
            { label: '₹2.5L', value: 250000 },
            { label: '₹5L', value: 500000 },
          ]}
          onChange={setDeductions}
          unit="₹"
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
            <AiCard
              text={`**How much more deduction do you need for the old regime to win?** At ${formatInr(grossIncome)} income, the new regime’s standard deduction is ${formatInr(REGIME_CONFIG.newStandardDeduction)}. The old regime needs total deductions above roughly ${formatInr(Math.round((r.newTax - r.oldTax + r.saving) / 0.3 + deductions))} to pull ahead — run the slider to find your break-even.`}
            />
            <AiCard
              text={`**The rebate threshold is the biggest lever.** Income up to ₹12 L is fully tax-free under the new regime thanks to the 87A rebate — an effective 0% rate even though slabs apply above ₹4 L. Under the old regime the nil-tax ceiling is ₹5 L. Once your income clears ₹12 L the new-regime advantage shrinks as the normal slab rates kick in.`}
            />
          </div>
          <div className="mt-3">
            <DisclosureBundle
              notAdvice={`For education only — not tax advice. An estimate at ${REGIME_CONFIG.asOf} rates; surcharge and special incomes are not modelled. Consult a qualified professional.`}
            />
          </div>
        </Section>

        {related.length > 0 && (
          <Section>
            <SectionHeader index="✦" title="Related Calculators" />
            <div className="flex gap-3 overflow-x-auto pb-1 sm:grid sm:grid-cols-2 sm:overflow-visible lg:grid-cols-4">
              {related.map((c) => (
                <RelatedCard
                  key={c.slug}
                  emoji={c.emoji}
                  name={c.name}
                  desc={c.sub}
                  accent="royal"
                  href={`/calculators/${c.slug}`}
                />
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

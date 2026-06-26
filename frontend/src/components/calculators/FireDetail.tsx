'use client';

/**
 * FireDetail — 'fire' view: Financial Independence / Retire Early calculator.
 * Estimates the corpus needed to sustain the user's current spending at their
 * chosen withdrawal rate, and how many years of saving/investing it takes to
 * reach that number.
 *
 * COMPLIANCE: an educational ESTIMATE on the user's own figures — not
 * investment, retirement, or financial advice. The withdrawal rate and assumed
 * return are the user's own assumptions, not DhanRadar predictions or
 * guarantees. The 4% rule is explicitly labelled a rule-of-thumb that the user
 * can change — not a recommendation.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeSip, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

export function FireDetail({ config }: { config: CalcConfig }) {
  const [annualExpense, setAnnualExpense] = React.useState(600000);
  const [withdrawalRate, setWithdrawalRate] = React.useState(4);
  const [currentCorpus, setCurrentCorpus] = React.useState(1000000);
  const [monthlySavings, setMonthlySavings] = React.useState(50000);
  const [assumedReturn, setAssumedReturn] = React.useState(12);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(() => {
    const fireNumber = annualExpense / (withdrawalRate / 100);
    // smallest whole year (0–60) where the accumulated corpus reaches the FIRE number
    let yearsToFire = 60;
    for (let y = 0; y <= 60; y++) {
      const fv = computeSip({
        monthlySip: monthlySavings,
        lumpSum: currentCorpus,
        years: y,
        annualRatePct: assumedReturn,
      }).futureValue;
      if (fv >= fireNumber) { yearsToFire = y; break; }
    }
    const finalCorpus = computeSip({
      monthlySip: monthlySavings,
      lumpSum: currentCorpus,
      years: yearsToFire,
      annualRatePct: assumedReturn,
    }).futureValue;
    // monthly income the FIRE corpus throws off at the chosen withdrawal rate
    const monthlyFromFire = fireNumber * (withdrawalRate / 100) / 12;
    return { fireNumber, yearsToFire, finalCorpus, monthlyFromFire };
  }, [annualExpense, withdrawalRate, currentCorpus, monthlySavings, assumedReturn]);

  const reset = () => {
    setAnnualExpense(600000);
    setWithdrawalRate(4);
    setCurrentCorpus(1000000);
    setMonthlySavings(50000);
    setAssumedReturn(12);
  };

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const yearsLabel = r.yearsToFire >= 60 ? '60+ yrs' : `${r.yearsToFire} yrs`;

  const excelTable: ExcelTable = {
    summary: `${config.name} — At ₹${(annualExpense / 100000).toFixed(0)}L/yr spending and ${withdrawalRate}% withdrawal rate, FIRE number is ${formatInr(r.fireNumber)}. Saving ${formatInr(monthlySavings)}/mo at ${assumedReturn}% assumed return on ${formatInr(currentCorpus)} starting corpus: ${yearsLabel} to FIRE.`,
    note: `Educational estimate only — not investment, retirement, or financial advice. The withdrawal rate (${withdrawalRate}%) and assumed return (${assumedReturn}%) are your own assumptions, not guarantees. The 4% rule is a rule-of-thumb, not a prescribed rate. Real markets vary.`,
    headers: ['Item', 'Amount'],
    rows: [
      ['Annual expense today', Math.round(annualExpense)],
      ['Withdrawal rate (your assumption)', withdrawalRate],
      ['FIRE number', Math.round(r.fireNumber)],
      ['Current corpus', Math.round(currentCorpus)],
      ['Monthly savings', Math.round(monthlySavings)],
      ['Years to FIRE (estimated)', r.yearsToFire >= 60 ? '60+' : r.yearsToFire],
      ['Projected corpus at FIRE', Math.round(r.finalCorpus)],
      ['Estimated monthly income at FIRE', Math.round(r.monthlyFromFire)],
    ],
    colFormats: ['text', 'num'],
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
        <h3 className="m-0 text-[15px] font-medium text-ink">Your FIRE Plan</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Enter your own numbers to estimate your FIRE number and the years it takes to get there.</p>

        <RangeField
          label="Annual Expense"
          tip="What you spend in a year today"
          value={annualExpense}
          min={100000}
          max={10000000}
          step={50000}
          format={formatInr}
          presets={[{ label: '₹6L', value: 600000 }, { label: '₹12L', value: 1200000 }, { label: '₹24L', value: 2400000 }]}
          onChange={setAnnualExpense}
          unit="₹"
        />
        <RangeField
          label="Withdrawal Rate (your assumption)"
          tip="A rule-of-thumb you can change — not a guarantee"
          value={withdrawalRate}
          min={2}
          max={8}
          step={0.25}
          format={(n) => `${n}%`}
          presets={[{ label: '3%', value: 3 }, { label: '3.5%', value: 3.5 }, { label: '4%', value: 4 }]}
          onChange={setWithdrawalRate}
          unit="%"
        />
        <RangeField
          label="Current Corpus"
          tip="What you've already saved"
          value={currentCorpus}
          min={0}
          max={1000000000}
          step={50000}
          format={formatInr}
          presets={[{ label: '₹0', value: 0 }, { label: '₹10L', value: 1000000 }, { label: '₹50L', value: 5000000 }, { label: '₹1Cr', value: 10000000 }]}
          onChange={setCurrentCorpus}
          unit="₹"
        />
        <RangeField
          label="Monthly Savings"
          tip="What you invest each month toward FIRE"
          value={monthlySavings}
          min={1000}
          max={1000000}
          step={1000}
          format={formatInr}
          presets={[{ label: '₹25K', value: 25000 }, { label: '₹50K', value: 50000 }, { label: '₹1L', value: 100000 }]}
          onChange={setMonthlySavings}
          unit="₹"
        />
        <RangeField
          label="Assumed Return (your assumption)"
          tip="Your assumption, not our prediction"
          value={assumedReturn}
          min={1}
          max={30}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[{ label: '10%', value: 10 }, { label: '12%', value: 12 }, { label: '15%', value: 15 }]}
          onChange={setAssumedReturn}
          unit="%"
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Kpi
            hero
            label="FIRE Number"
            value={formatInr(r.fireNumber)}
            sub={`${(100 / withdrawalRate).toFixed(0)}× your annual expense`}
          />
          <Kpi
            label="Years to FIRE"
            value={yearsLabel}
            sub={`At ${formatInr(monthlySavings)}/mo savings`}
            accent="pos"
          />
          <Kpi
            label="Monthly Savings"
            value={formatInr(monthlySavings)}
            sub="Your monthly contribution toward FIRE"
          />
          <Kpi
            label="Income at FIRE"
            value={`${formatInr(r.monthlyFromFire)}/mo`}
            sub={`At ${withdrawalRate}% withdrawal (your assumption)`}
          />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Breakdown" />
          <Panel>
            {row('Annual expense today', formatInr(annualExpense))}
            {row(`Withdrawal rate (your assumption)`, `${withdrawalRate}%`)}
            {row('FIRE number', formatInr(r.fireNumber), true)}
            {row('Current corpus', formatInr(currentCorpus))}
            {row('Monthly savings', `${formatInr(monthlySavings)}/mo`)}
            {row('Years to reach FIRE (estimated)', yearsLabel, true)}
            <SoWhat>
              Your FIRE number is your annual expense divided by your withdrawal rate — at {withdrawalRate}%, that is{' '}
              <b className="font-semibold text-ink">{(100 / withdrawalRate).toFixed(0)}×</b> your yearly spending.
              The 4% rule is a widely-cited starting point, not a prescribed rate — you can change it above to see how it shifts the target.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text="**Saving more OR spending less both shorten your years-to-FIRE.** A 10% cut in annual expense shrinks the FIRE number and frees up more savings at the same time — a double effect." />
            <AiCard text={`**Your assumed return (${assumedReturn}%) and withdrawal rate (${withdrawalRate}%) are your own figures, not a DhanRadar prediction.** Small changes in either can shift the timeline by years — try a few combinations to understand the range.`} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment or retirement advice. The withdrawal rate and return are your own assumptions, not guarantees; real markets vary. The 4% rule is a rule-of-thumb, not a prescribed rate. Consult a qualified financial professional before making retirement decisions." />
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

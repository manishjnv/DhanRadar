'use client';

/**
 * CorpusDetail — 'corpus' view (E2/E3 inverse): corpus needed to fund a
 * retirement income. Uses corpusForIncome from @/lib/finance/swp.
 *
 * COMPLIANCE: an educational ESTIMATE on the user's own assumptions — not
 * investment or retirement advice. Return and inflation are labelled as
 * the user's own figures; no advisory verbs.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { corpusForIncome, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

export function CorpusDetail({ config }: { config: CalcConfig }) {
  const [income, setIncome] = React.useState(50000);
  const [years, setYears] = React.useState(25);
  const [postReturn, setPostReturn] = React.useState(7);
  const [inflation, setInflation] = React.useState(6);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(
    () => corpusForIncome({ monthlyWithdrawal: income, years, annualRatePct: postReturn, inflationPct: inflation }),
    [income, years, postReturn, inflation],
  );

  const reset = () => { setIncome(50000); setYears(25); setPostReturn(7); setInflation(6); };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — ₹${income.toLocaleString('en-IN')}/mo income for ${years} yrs at ${postReturn}% return, ${inflation}% inflation: corpus needed ${formatInr(r.corpusNeeded)}.`,
    note: 'Educational estimate only — not investment or retirement advice. Return and inflation are your own assumptions; real market returns vary.',
    headers: ['Item', 'Amount'],
    rows: [
      ['Desired monthly income (today)', income],
      ['Years of retirement', years],
      ['Post-retirement return (your assumption)', `${postReturn}%`],
      ['Inflation (your assumption)', `${inflation}%`],
      ['Corpus to last the period', Math.round(r.corpusNeeded)],
      ['Corpus to never deplete (perpetual)', Math.round(r.perpetualCorpus)],
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
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Retirement Income</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Enter your income need and assumptions — the result is your required corpus.</p>

        <RangeField
          label="Desired Monthly Income"
          tip="The income you want, in today's money"
          value={income}
          min={5000}
          max={1000000}
          step={1000}
          format={formatInr}
          presets={[{ label: '₹30K', value: 30000 }, { label: '₹50K', value: 50000 }, { label: '₹1L', value: 100000 }]}
          onChange={setIncome}
          unit="₹"
        />
        <RangeField
          label="Years of Retirement"
          tip="How many years it must last"
          value={years}
          min={5}
          max={50}
          step={1}
          format={(n) => `${n} yrs`}
          presets={[{ label: '20 yrs', value: 20 }, { label: '25 yrs', value: 25 }, { label: '30 yrs', value: 30 }]}
          onChange={setYears}
          unit="yrs"
        />
        <RangeField
          label="Post-Retirement Return"
          tip="Assumed return on the corpus (your assumption)"
          value={postReturn}
          min={1}
          max={20}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[{ label: '6%', value: 6 }, { label: '7%', value: 7 }, { label: '8%', value: 8 }]}
          onChange={setPostReturn}
          unit="%"
        />
        <RangeField
          label="Inflation"
          tip="How fast your income need rises"
          value={inflation}
          min={0}
          max={12}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[{ label: '4%', value: 4 }, { label: '6%', value: 6 }, { label: '8%', value: 8 }]}
          onChange={setInflation}
          unit="%"
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Kpi hero label="Corpus Required" value={formatInr(r.corpusNeeded)} sub={`To draw ${formatInr(income)}/mo for ${years} yrs`} />
          <Kpi label="Monthly Income" value={`${formatInr(income)}/mo`} sub="Income in today's money" accent="pos" />
          <Kpi label="Never-Deplete Corpus" value={formatInr(r.perpetualCorpus)} sub="Lives off returns alone" />
          <Kpi label="Years Funded" value={`${years} yrs`} sub="Retirement horizon" />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Breakdown" />
          <Panel>
            {row('Desired monthly income', formatInr(income))}
            {row('Years of retirement', `${years} yrs`)}
            {row('Post-retirement return (your assumption)', `${postReturn}%`)}
            {row('Inflation (your assumption)', `${inflation}%`)}
            {row('Corpus to last the period', formatInr(r.corpusNeeded), true)}
            {row('Corpus to never deplete', formatInr(r.perpetualCorpus), true)}
            <SoWhat>
              The corpus is the <b className="font-semibold text-ink">present value</b> of every future (inflating) withdrawal discounted at your assumed return. A larger corpus lasts longer — and the never-deplete figure is what you need to live off returns alone, leaving principal untouched.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text="**A higher assumed return lowers the corpus needed** — but also raises the risk. If real returns fall short of your assumption, the corpus depletes sooner. Use a conservative return figure as your base." />
            <AiCard text="**Fewer years in retirement means a smaller corpus** — but longevity is unpredictable. Planning for 30+ years gives you a cushion; the never-deplete corpus is the safest target if you are unsure how long you need it." />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment or retirement advice. The return and inflation are your own assumptions; real markets vary. Consult a qualified financial planner." />
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

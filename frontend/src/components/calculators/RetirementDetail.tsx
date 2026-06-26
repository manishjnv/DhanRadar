'use client';

/**
 * RetirementDetail — 'retirement' view (E1 + E3): accumulate a corpus over your
 * working years, then draw it down through retirement. Shows the corpus needed,
 * the monthly SIP to get there, and how long the corpus lasts.
 *
 * COMPLIANCE: an educational ESTIMATE on the user's own figures — not investment
 * or retirement advice. All returns and inflation are the user's own assumptions,
 * not predictions. No advisory verbs; no readiness verdict; numbers only.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { corpusForIncome, computeSwp, formatInr } from '@/lib/finance';
import { computeSip } from '@/lib/finance';
import { solveGoal } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

export function RetirementDetail({ config }: { config: CalcConfig }) {
  const [curAge, setCurAge] = React.useState(30);
  const [retAge, setRetAge] = React.useState(60);
  const [lifeExp, setLifeExp] = React.useState(85);
  const [curExpense, setCurExpense] = React.useState(50000);
  const [infl, setInfl] = React.useState(6);
  const [preReturn, setPreReturn] = React.useState(12);
  const [postReturn, setPostReturn] = React.useState(7);
  const [existingCorpus, setExistingCorpus] = React.useState(0);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(() => {
    const yearsToRet = Math.max(retAge - curAge, 0);
    const retYears = Math.max(lifeExp - retAge, 1);
    const monthlyExpenseAtRet = curExpense * Math.pow(1 + infl / 100, yearsToRet);
    const { corpusNeeded } = corpusForIncome({
      monthlyWithdrawal: monthlyExpenseAtRet,
      years: retYears,
      annualRatePct: postReturn,
      inflationPct: infl,
    });
    const existingFv = computeSip({
      monthlySip: 0,
      lumpSum: existingCorpus,
      years: yearsToRet,
      annualRatePct: preReturn,
    }).futureValue;
    const shortfall = Math.max(corpusNeeded - existingFv, 0);
    // shortfall is already in future rupees — pass inflationPct:0 to avoid double-inflating
    const { requiredMonthly } = solveGoal({
      targetToday: shortfall,
      years: yearsToRet,
      annualRatePct: preReturn,
      inflationPct: 0,
    });
    const lastsCheck = computeSwp({
      corpus: corpusNeeded,
      monthlyWithdrawal: monthlyExpenseAtRet,
      annualRatePct: postReturn,
      inflationPct: infl,
    });
    return { yearsToRet, retYears, monthlyExpenseAtRet, corpusNeeded, existingFv, shortfall, requiredMonthly, lastsCheck };
  }, [curAge, retAge, lifeExp, curExpense, infl, preReturn, postReturn, existingCorpus]);

  const reset = () => {
    setCurAge(30); setRetAge(60); setLifeExp(85); setCurExpense(50000);
    setInfl(6); setPreReturn(12); setPostReturn(7); setExistingCorpus(0);
  };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const corpusLastsYrs = r.lastsCheck.sustainable
    ? r.retYears
    : Math.floor(r.lastsCheck.monthsLasted / 12);
  const corpusLastsLabel = r.lastsCheck.sustainable
    ? `${r.retYears}+ yrs`
    : `~${corpusLastsYrs} yrs`;
  const corpusLastsSub = `To age ${retAge + corpusLastsYrs}`;

  const excelTable: ExcelTable = {
    summary: `${config.name} — retire at ${retAge}, live to ${lifeExp}; corpus needed ${formatInr(r.corpusNeeded)}, monthly SIP ${formatInr(r.requiredMonthly)}/mo for ${r.yearsToRet} yrs (your assumptions: pre-ret ${preReturn}%, post-ret ${postReturn}%, inflation ${infl}%).`,
    note: 'Educational estimate only — not investment or retirement advice. Returns and inflation are your own assumptions; real markets vary. Consult a qualified professional.',
    headers: ['Item', 'Amount'],
    rows: [
      ['Years to retirement', r.yearsToRet],
      ['Monthly expense at retirement (your assumed inflation)', Math.round(r.monthlyExpenseAtRet)],
      ['Corpus needed', Math.round(r.corpusNeeded)],
      ['Existing corpus grows to', Math.round(r.existingFv)],
      ['Shortfall to fund', Math.round(r.shortfall)],
      ['Required monthly SIP', Math.round(r.requiredMonthly)],
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
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Retirement</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          Two phases — build a corpus while working, then draw it down in retirement. All figures are your own assumptions.
        </p>

        <RangeField
          label="Current Age"
          tip="Your age today"
          value={curAge}
          min={18}
          max={60}
          step={1}
          format={(n) => `${n}`}
          presets={[{ label: '25', value: 25 }, { label: '30', value: 30 }, { label: '35', value: 35 }, { label: '40', value: 40 }]}
          onChange={setCurAge}
        />
        <RangeField
          label="Retirement Age"
          tip="When you'll stop working"
          value={retAge}
          min={40}
          max={70}
          step={1}
          format={(n) => `${n}`}
          presets={[{ label: '55', value: 55 }, { label: '60', value: 60 }, { label: '65', value: 65 }]}
          onChange={setRetAge}
        />
        <RangeField
          label="Life Expectancy"
          tip="Plan your corpus to last until here"
          value={lifeExp}
          min={60}
          max={100}
          step={1}
          format={(n) => `${n}`}
          presets={[{ label: '80', value: 80 }, { label: '85', value: 85 }, { label: '90', value: 90 }]}
          onChange={setLifeExp}
        />
        <RangeField
          label="Current Monthly Expense"
          tip="What you spend per month today"
          value={curExpense}
          min={5000}
          max={1000000}
          step={1000}
          format={formatInr}
          presets={[{ label: '₹30K', value: 30000 }, { label: '₹50K', value: 50000 }, { label: '₹1L', value: 100000 }]}
          onChange={setCurExpense}
          unit="₹"
        />
        <RangeField
          label="Inflation (your assumption)"
          tip="How fast costs rise — your own assumption, not a prediction"
          value={infl}
          min={0}
          max={12}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[{ label: '4%', value: 4 }, { label: '6%', value: 6 }, { label: '8%', value: 8 }]}
          onChange={setInfl}
          unit="%"
        />
        <RangeField
          label="Pre-Retirement Return (your assumption)"
          tip="Assumed return while saving — your own assumption, not a DhanRadar prediction"
          value={preReturn}
          min={1}
          max={30}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[{ label: '10%', value: 10 }, { label: '12%', value: 12 }, { label: '15%', value: 15 }]}
          onChange={setPreReturn}
          unit="%"
        />
        <RangeField
          label="Post-Retirement Return (your assumption)"
          tip="Assumed return after retiring — your own assumption, not a DhanRadar prediction"
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
          label="Existing Corpus"
          tip="What you've already saved for retirement"
          value={existingCorpus}
          min={0}
          max={1000000000}
          step={50000}
          format={formatInr}
          presets={[{ label: '₹0', value: 0 }, { label: '₹10L', value: 1000000 }, { label: '₹50L', value: 5000000 }, { label: '₹1Cr', value: 10000000 }]}
          onChange={setExistingCorpus}
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
            label="Corpus Needed at Retirement"
            value={formatInr(r.corpusNeeded)}
            sub={`By age ${retAge}`}
          />
          <Kpi
            label="Monthly SIP to Get There"
            value={`${formatInr(r.requiredMonthly)}/mo`}
            accent="pos"
            sub={`For ${r.yearsToRet} yrs`}
          />
          <Kpi
            label="Monthly Expense Then"
            value={formatInr(r.monthlyExpenseAtRet)}
            sub={`${formatInr(curExpense)} today at ${infl}% inflation (your assumption)`}
          />
          <Kpi
            label="Corpus Lasts"
            value={corpusLastsLabel}
            sub={corpusLastsSub}
          />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Two-Phase Breakdown" />
          <Panel>
            {row('Years to retirement', `${r.yearsToRet} yrs`)}
            {row('Monthly expense at retirement', formatInr(r.monthlyExpenseAtRet))}
            {row('Corpus needed', formatInr(r.corpusNeeded), true)}
            {existingCorpus > 0 && row('Your existing corpus grows to', formatInr(r.existingFv))}
            {row('Shortfall to fund', formatInr(r.shortfall), true)}
            <SoWhat>
              Phase 1 (accumulation): invest a monthly SIP for <b className="font-semibold text-ink">{r.yearsToRet} years</b> at your assumed <b className="font-semibold text-ink">{preReturn}%</b> return to build the corpus. Phase 2 (drawdown): the corpus earns <b className="font-semibold text-ink">{postReturn}%</b> while paying your inflation-adjusted expenses — on these assumptions it lasts <b className="font-semibold text-ink">{corpusLastsLabel}</b>.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={`**Retiring ${Math.min(r.yearsToRet + 2, 70 - curAge) - r.yearsToRet > 0 ? 2 : 0} years later** (age ${Math.min(retAge + 2, 70)}) extends your accumulation phase and shortens your drawdown — both reduce the monthly SIP needed on your figures.`} />
            <AiCard text={`Your **post-retirement return assumption (${postReturn}%)** versus inflation (${infl}%) gives a real return of about ${(postReturn - infl).toFixed(1)}%. A wider gap means the corpus depletes more slowly; a narrower gap puts more pressure on the corpus size.`} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment or retirement advice. Returns and inflation are your own assumptions; real markets vary. Consult a qualified professional." />
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

'use client';

/**
 * PassiveIncomeDetail — 'passive-income' view (E9/E3): how much monthly income
 * a corpus can generate at a given withdrawal rate, and whether that income is
 * sustainable (corpus earns more than you withdraw). Uses computeSwp.
 *
 * COMPLIANCE: an educational ESTIMATE on the user's own assumptions — not
 * investment advice. Withdrawal rate and expected return are explicitly labelled
 * as the user's own inputs; income is not guaranteed.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeSwp, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

export function PassiveIncomeDetail({ config }: { config: CalcConfig }) {
  const [corpus, setCorpus] = React.useState(10_000_000);
  const [withdrawalRate, setWithdrawalRate] = React.useState(4);
  const [expectedReturn, setExpectedReturn] = React.useState(8);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const { annualIncome, monthlyIncome, swp } = React.useMemo(() => {
    const annual = corpus * (withdrawalRate / 100);
    const monthly = annual / 12;
    const result = computeSwp({
      corpus,
      monthlyWithdrawal: monthly,
      annualRatePct: expectedReturn,
    });
    return { annualIncome: annual, monthlyIncome: monthly, swp: result };
  }, [corpus, withdrawalRate, expectedReturn]);

  const neverDepletes = swp.sustainable;

  const reset = () => {
    setCorpus(10_000_000);
    setWithdrawalRate(4);
    setExpectedReturn(8);
  };

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const lastsLabel = neverDepletes
    ? 'Indefinitely'
    : `~${Math.floor(swp.monthsLasted / 12)} yrs`;

  const lastsSubLabel = neverDepletes
    ? `Income ≤ ${expectedReturn}% earned`
    : `Withdrawal above what it earns`;

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${formatInr(corpus)} corpus at ${withdrawalRate}% withdrawal (your assumption): ${formatInr(monthlyIncome)}/month, ${neverDepletes ? 'sustainable indefinitely' : `lasts ~${Math.floor(swp.monthsLasted / 12)} years`}.`,
    note: `Educational estimate only — not investment advice. The ${withdrawalRate}% withdrawal rate and ${expectedReturn}% expected return are your own assumptions; real markets vary and income is not guaranteed.`,
    headers: ['Item', 'Amount'],
    rows: [
      ['Corpus', Math.round(corpus)],
      ['Withdrawal rate (your assumption)', withdrawalRate],
      ['Annual income', Math.round(annualIncome)],
      ['Monthly income', Math.round(monthlyIncome)],
      ['Expected return (your assumption)', expectedReturn],
      ['Outlook', neverDepletes ? 'Sustainable indefinitely' : `Depletes in ~${Math.floor(swp.monthsLasted / 12)} years`],
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
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Corpus</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          Enter your corpus and your own assumptions to see what monthly income it could generate.
        </p>

        <RangeField
          label="Corpus"
          tip="The pot you draw income from"
          value={corpus}
          min={100_000}
          max={1_000_000_000}
          step={100_000}
          format={formatInr}
          presets={[
            { label: '₹50L', value: 5_000_000 },
            { label: '₹1Cr', value: 10_000_000 },
            { label: '₹2.5Cr', value: 25_000_000 },
            { label: '₹5Cr', value: 50_000_000 },
          ]}
          onChange={setCorpus}
          unit="₹"
        />

        <RangeField
          label="Withdrawal Rate"
          tip="The % of corpus you take each year (your assumption)"
          value={withdrawalRate}
          min={1}
          max={10}
          step={0.25}
          format={(n) => `${n}%`}
          presets={[
            { label: '3%', value: 3 },
            { label: '4%', value: 4 },
            { label: '5%', value: 5 },
            { label: '6%', value: 6 },
          ]}
          onChange={setWithdrawalRate}
          unit="%"
        />

        <RangeField
          label="Expected Return"
          tip="Assumed return the corpus earns (your assumption)"
          value={expectedReturn}
          min={1}
          max={20}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[
            { label: '6%', value: 6 },
            { label: '7%', value: 7 },
            { label: '8%', value: 8 },
            { label: '10%', value: 10 },
          ]}
          onChange={setExpectedReturn}
          unit="%"
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions
            vals={{ corpus, withdrawalRate, expectedReturn }}
            name={config.name}
            targetRef={resultRef}
            table={excelTable}
          />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            hero
            label="Monthly Income"
            value={formatInr(monthlyIncome)}
            sub={`${withdrawalRate}% of ${formatInr(corpus)} a year`}
          />
          <Kpi
            label="Annual Income"
            value={formatInr(annualIncome)}
            sub="Your yearly withdrawal"
            accent="pos"
          />
          <Kpi
            label="Withdrawal Rate"
            value={`${withdrawalRate}%`}
            sub="Your assumption"
          />
          <Kpi
            label="Lasts"
            value={lastsLabel}
            sub={lastsSubLabel}
          />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Breakdown" />
          <Panel>
            {row('Corpus', formatInr(corpus))}
            {row('Withdrawal rate (your assumption)', `${withdrawalRate}%`)}
            {row('Annual income', formatInr(annualIncome), true)}
            {row('Monthly income', formatInr(monthlyIncome), true)}
            {row('Expected return (your assumption)', `${expectedReturn}%`)}
            {row('Outlook', neverDepletes ? 'Sustainable indefinitely' : `Depletes in ~${Math.floor(swp.monthsLasted / 12)} years`, true)}
            <SoWhat>
              Drawing no more than what your corpus earns at{' '}
              <b className="font-semibold text-ink">{expectedReturn}%</b> keeps the principal
              intact. Your withdrawal rate of{' '}
              <b className="font-semibold text-ink">{withdrawalRate}%</b> is{' '}
              {neverDepletes
                ? 'within that limit — income can continue indefinitely on your assumptions.'
                : 'above what the corpus earns — the principal will shrink over time.'}
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard
              text={`**The ${withdrawalRate}% withdrawal rate is your own assumption** — a lower rate (e.g. 3–4%) leaves a larger buffer between what you withdraw and what the corpus earns, making income last longer under your return assumption.`}
            />
            <AiCard
              text={`**A larger corpus or a higher assumed return** could raise the monthly income or extend how long it lasts — but the actual return a corpus earns will vary with markets and is not guaranteed. These are illustrative figures on your inputs.`}
            />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. The withdrawal rate and return are your own assumptions; real markets vary and income is not guaranteed." />
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

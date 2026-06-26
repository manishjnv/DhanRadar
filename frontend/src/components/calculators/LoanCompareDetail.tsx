'use client';

/**
 * LoanCompareDetail — bespoke 'loan-compare' view. Two loan offers side by side
 * (amount / rate / tenure each), each costed via `computeLoan`, with a neutral
 * factual comparison of the user's own numbers.
 *
 * COMPLIANCE: a factual cost comparison of the user's inputs — NOT a recommendation
 * to pick either loan. No advisory verbs; disclaimer beside the result.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Panel, RangeField, SoWhat, RelatedCard } from './ui';
import { computeLoan, formatInr, formatInrShort } from '@/lib/finance';
import { type CalcConfig, getConfig, fmtValue, fmtPreset, fmtUnit, type Fmt } from './registry';

type Loan = { amount: number; rate: number; tenure: number };
type FieldKey = keyof Loan;

const FIELDS: { key: FieldKey; label: string; tip: string; min: number; max: number; step: number; fmt: Fmt; presets: number[] }[] = [
  { key: 'amount', label: 'Loan Amount', tip: 'How much you borrow', min: 100000, max: 100000000, step: 100000, fmt: 'inr', presets: [2500000, 5000000, 7500000, 10000000] },
  { key: 'rate', label: 'Interest Rate', tip: 'The yearly interest rate', min: 5, max: 20, step: 0.05, fmt: 'pct', presets: [7.5, 8.5, 9.5, 10.5] },
  { key: 'tenure', label: 'Tenure', tip: 'Years to repay', min: 1, max: 30, step: 1, fmt: 'years', presets: [10, 15, 20, 25, 30] },
];

function LoanColumn({ title, accent, loan, onChange }: { title: string; accent: boolean; loan: Loan; onChange: (k: FieldKey, v: number) => void }) {
  const res = computeLoan({ principal: loan.amount, annualRatePct: loan.rate, years: loan.tenure });
  return (
    <Panel className={accent ? 'ring-2 ring-emerald/40' : undefined}>
      <div className="mb-3 flex items-center justify-between">
        <div className="text-[15px] font-medium text-ink">{title}</div>
        {accent && <span className="rounded-md bg-emerald/15 px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wide text-emerald">Lower total cost</span>}
      </div>
      {FIELDS.map((f) => (
        <RangeField
          key={f.key}
          label={f.label}
          tip={f.tip}
          value={loan[f.key]}
          min={f.min}
          max={f.max}
          step={f.step}
          format={(n) => fmtValue(f.fmt, n)}
          presets={f.presets.map((v) => ({ label: fmtPreset(f.fmt, v), value: v }))}
          onChange={(n) => onChange(f.key, n)}
          unit={fmtUnit(f.fmt)}
        />
      ))}
      <div className="mt-1 space-y-2 border-t border-line pt-3">
        <Row label="Monthly EMI" value={`${formatInr(res.emi)}/mo`} strong />
        <Row label="Total Interest" value={formatInr(res.totalInterest)} />
        <Row label="Total Payment" value={formatInr(res.totalPayment)} />
      </div>
    </Panel>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-small text-ink-secondary">{label}</span>
      <span className={`font-mono text-small ${strong ? 'font-bold text-ink' : 'font-semibold text-ink-secondary'}`}>{value}</span>
    </div>
  );
}

export function LoanCompareDetail({ config }: { config: CalcConfig }) {
  const [a, setA] = React.useState<Loan>({ amount: 5000000, rate: 8.5, tenure: 20 });
  const [b, setB] = React.useState<Loan>({ amount: 5000000, rate: 9, tenure: 15 });

  const ra = computeLoan({ principal: a.amount, annualRatePct: a.rate, years: a.tenure });
  const rb = computeLoan({ principal: b.amount, annualRatePct: b.rate, years: b.tenure });
  const aCheaper = ra.totalPayment <= rb.totalPayment;
  const diff = Math.abs(ra.totalPayment - rb.totalPayment);
  const emiDiff = Math.abs(ra.emi - rb.emi);

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  return (
    <div className="w-full">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <LoanColumn title="Loan A" accent={aCheaper} loan={a} onChange={(k, v) => setA((s) => ({ ...s, [k]: v }))} />
        <LoanColumn title="Loan B" accent={!aCheaper} loan={b} onChange={(k, v) => setB((s) => ({ ...s, [k]: v }))} />
      </div>

      <Section className="mt-[18px]">
        <SectionHeader index="✦" title="The Comparison" />
        <Panel>
          <SoWhat>
            <b className="font-semibold text-ink">Loan {aCheaper ? 'A' : 'B'}</b> costs <b className="font-semibold text-ink">{formatInr(diff)}</b> less in total over its term. Its EMI differs by <b className="font-semibold text-ink">{formatInrShort(emiDiff)}/mo</b> — a lower EMI usually means a longer tenure and more total interest, so weigh monthly affordability against total cost. These are your own numbers, not a recommendation.
          </SoWhat>
          <div className="mt-3.5 overflow-hidden rounded-[14px] border border-line">
            <table className="w-full border-collapse text-small">
              <thead>
                <tr>
                  {['', 'Loan A', 'Loan B'].map((h, i) => (
                    <th key={h || 'm'} className={`border-b-2 border-line bg-surface-2 px-3.5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-ink-muted ${i === 0 ? 'text-left' : 'text-right'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ['Monthly EMI', `${formatInr(ra.emi)}`, `${formatInr(rb.emi)}`],
                  ['Total Interest', formatInr(ra.totalInterest), formatInr(rb.totalInterest)],
                  ['Total Payment', formatInr(ra.totalPayment), formatInr(rb.totalPayment)],
                ].map((row) => (
                  <tr key={row[0]} className="hover:bg-surface-2">
                    <td className="border-b border-line px-3.5 py-2.5 text-left font-semibold text-ink">{row[0]}</td>
                    <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-semibold text-ink">{row[1]}</td>
                    <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-semibold text-ink">{row[2]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </Section>

      <Section>
        <DisclosureBundle notAdvice="For education only — not financial advice. This is a factual cost comparison of the numbers you entered, not a recommendation to choose either loan. Lenders' actual terms, fees, and eligibility vary." />
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
  );
}

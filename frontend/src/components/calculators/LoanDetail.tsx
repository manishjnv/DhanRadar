'use client';

/**
 * LoanDetail — the config-driven result view for the E7 loan family (Home Loan
 * EMI). Computes EMI + amortization via `computeLoan` and shows the EMI, total
 * interest, the principal-vs-interest split, and a year-by-year schedule.
 *
 * COMPLIANCE: figures are the USER's own computed numbers (not a DhanRadar fund
 * score). No advisory verbs; the disclaimer + What-If sit beside the result and
 * the AI cards are templated from the user's own inputs (no LLM).
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, Donut, WhatIfCard, AiCard, RelatedCard, SoWhat } from './ui';
import { computeLoan, formatInr, formatInrShort } from '@/lib/finance';
import { type CalcConfig, getConfig, fmtValue, fmtPreset } from './registry';

export function LoanDetail({ config }: { config: CalcConfig }) {
  const initVals = React.useCallback(() => {
    const o: Record<string, number> = {};
    config.inputs.forEach((inp) => { o[inp.key] = inp.default; });
    return o;
  }, [config]);

  const [vals, setVals] = React.useState<Record<string, number>>(initVals);

  const principal = vals.loanAmount ?? 0;
  const ratePct = vals.loanRate ?? 0;
  const tenure = vals.tenure ?? 0;

  const result = React.useMemo(
    () => computeLoan({ principal, annualRatePct: ratePct, years: tenure }),
    [principal, ratePct, tenure],
  );
  const { emi, totalInterest, totalPayment } = result;
  const interestPct = principal > 0 ? Math.round((totalInterest / principal) * 100) : 0;
  const interestShare = totalPayment > 0 ? Math.round((totalInterest / totalPayment) * 100) : 0;

  const base = { principal, annualRatePct: ratePct, years: tenure };
  const interestWith = (patch: Partial<typeof base>) => computeLoan({ ...base, ...patch }).totalInterest;
  const emiWith = (patch: Partial<typeof base>) => computeLoan({ ...base, ...patch }).emi;

  // What-if — total interest under one nudged input (less interest = good).
  const card = (name: string, val: string, ti: number) => {
    const d = ti - totalInterest;
    return { name, val, result: formatInrShort(ti), delta: `${formatInrShort(Math.abs(d))} ${d <= 0 ? 'less' : 'more'} interest`, up: d <= 0 };
  };
  const shorter = Math.max(tenure - 5, 1);
  const whatIf = [
    card('Rate 0.5% lower', `${Math.max(ratePct - 0.5, 0)}%`, interestWith({ annualRatePct: Math.max(ratePct - 0.5, 0) })),
    card('Rate 0.5% higher', `${ratePct + 0.5}%`, interestWith({ annualRatePct: ratePct + 0.5 })),
    card('5 years shorter', `${shorter} yrs`, interestWith({ years: shorter })),
    card('5 years longer', `${tenure + 5} yrs`, interestWith({ years: tenure + 5 })),
    card('Borrow 10% less', formatInrShort(principal * 0.9), interestWith({ principal: principal * 0.9 })),
  ];

  // AI insights — templated from the user's OWN numbers (no LLM call, no advice).
  const ai = [
    `**Repaying in ${shorter} years** instead of ${tenure} raises the EMI to about **${formatInrShort(emiWith({ years: shorter }))}/mo**, but cuts total interest by **${formatInrShort(totalInterest - interestWith({ years: shorter }))}**.`,
    `A **0.5% higher rate** adds about **${formatInrShort(interestWith({ annualRatePct: ratePct + 0.5 }) - totalInterest)}** to the interest over the whole loan.`,
    `Over ${tenure} ${tenure === 1 ? 'year' : 'years'} you'd pay **${formatInrShort(totalInterest)}** in interest — about **${interestPct}%** on top of the ${formatInrShort(principal)} you borrow.`,
  ];

  const rows = result.series.filter((p) => p.year >= 1).map((p) => ({
    year: p.year,
    principal: formatInrShort(p.principalPaid),
    interest: formatInrShort(p.interestPaid),
    balance: formatInrShort(p.balance),
  }));

  const reset = () => setVals(initVals());
  const setKey = (k: string, v: number) => setVals((s) => ({ ...s, [k]: v }));
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* INPUT PANEL */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Loan</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the sliders — the EMI updates instantly.</p>

        {config.inputs.map((inp) => (
          <RangeField
            key={inp.key}
            label={inp.label}
            tip={inp.tip}
            value={vals[inp.key]}
            min={inp.min}
            max={inp.max}
            step={inp.step}
            format={(n) => fmtValue(inp.fmt, n)}
            presets={inp.presets.map((v) => ({ label: fmtPreset(inp.fmt, v), value: v }))}
            onChange={(n) => setKey(inp.key, n)}
          />
        ))}

        <div className="flex gap-2">
          <Btn variant="pri" className="flex-1">Calculate</Btn>
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <Btn aria-label="Export results">⬇</Btn>
          <Btn aria-label="Share results">↗</Btn>
        </div>
      </Panel>

      {/* RESULT PANEL */}
      <div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi hero label="Monthly EMI" value={`${formatInr(emi)}/mo`} sub={`On ${formatInr(principal)} at ${ratePct}% for ${tenure} ${tenure === 1 ? 'year' : 'years'}`} />
          <Kpi label="Total Interest" value={formatInr(totalInterest)} sub="Paid over the loan" />
          <Kpi label="Total Payment" value={formatInr(totalPayment)} sub="Principal + interest" />
          <Kpi label="Interest vs Loan" value={`${interestPct}%`} sub="Interest as % of amount borrowed" />
        </div>

        {/* Principal vs interest split */}
        <Section className="mt-3.5">
          <SectionHeader index="✦" title="What You Actually Pay" />
          <Panel>
            <div className="flex flex-col items-center gap-5 sm:flex-row">
              <Donut invested={Math.max(principal, 0)} profit={Math.max(totalInterest, 0)} />
              <div className="flex-1 self-stretch">
                <div className="flex items-center gap-2.5 border-b border-line py-2.5">
                  <span className="h-3 w-3 rounded-[3px] bg-surface-3" />
                  <span className="flex-1 text-small font-semibold text-ink">Principal (what you borrow)</span>
                  <span className="font-mono font-bold text-ink">{formatInr(principal)}</span>
                  <span className="w-12 text-right font-mono text-ink-muted">{100 - interestShare}%</span>
                </div>
                <div className="flex items-center gap-2.5 py-2.5">
                  <span className="h-3 w-3 rounded-[3px] bg-royal" />
                  <span className="flex-1 text-small font-semibold text-ink">Interest (cost of the loan)</span>
                  <span className="font-mono font-bold text-royal">{formatInr(totalInterest)}</span>
                  <span className="w-12 text-right font-mono text-ink-muted">{interestShare}%</span>
                </div>
                <SoWhat>
                  <b className="font-semibold text-ink">{interestShare}% of everything you pay is interest.</b> A shorter tenure or a lower rate cuts this — see the What-If below.
                </SoWhat>
              </div>
            </div>
          </Panel>
        </Section>

        {/* What if */}
        <Section className="mt-[18px]">
          <SectionHeader index="✦" title="What If…" info="What changes the interest you pay" />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {whatIf.map((w) => <WhatIfCard key={w.name} {...w} />)}
          </div>
        </Section>

        {/* AI insights */}
        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {ai.map((t, i) => <AiCard key={i} text={t} />)}
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not financial advice. These figures illustrate how your own inputs change an EMI and the interest paid; they are not a loan recommendation. Lenders' actual terms, fees, and rates vary." />
          </div>
        </Section>

        {/* Amortization table */}
        <Section>
          <SectionHeader index="✦" title="Year-by-Year Repayment" />
          <div className="max-h-[340px] overflow-auto rounded-[14px] border border-line">
            <table className="w-full border-collapse text-small">
              <thead>
                <tr>
                  {['Year', 'Principal Paid', 'Interest Paid', 'Balance Left'].map((h, i) => (
                    <th key={h} className={`sticky top-0 z-[2] border-b-2 border-line bg-surface-2 px-3.5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-ink-muted ${i === 0 ? 'text-left' : 'text-right'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.year} className="hover:bg-surface-2">
                    <td className="border-b border-line px-3.5 py-2.5 text-left font-semibold text-ink">Year {r.year}</td>
                    <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-semibold text-ink">{r.principal}</td>
                    <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-semibold text-royal">{r.interest}</td>
                    <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-semibold text-ink-muted">{r.balance}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        {/* Related */}
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

        {/* Sticky bar */}
        <div className="fixed bottom-[18px] left-1/2 z-[55] flex -translate-x-1/2 items-center gap-3.5 rounded-2xl bg-navy/95 px-4 py-3 shadow-[0_24px_60px_-20px_rgba(15,23,42,.45)] backdrop-blur">
          <div className="text-white">
            <small className="block text-[10px] font-semibold uppercase tracking-[0.04em] text-slate-400">Monthly EMI</small>
            <span className="text-small font-bold">{formatInrShort(emi)}/mo</span>
          </div>
          <Btn variant="pri" className="px-3.5">Calculate</Btn>
        </div>
      </div>
    </div>
  );
}

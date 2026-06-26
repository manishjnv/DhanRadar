'use client';

/**
 * PrepaymentDetail — config-driven 'prepayment' view (E7 family). Shows how a
 * one-time lump and/or extra monthly payment shortens the loan tenure and cuts
 * total interest (keep-EMI mode), via `computePrepayment`.
 *
 * COMPLIANCE: the figures are the user's own computed numbers; no advisory verbs;
 * disclaimer + What-If beside the result; AI cards templated (no LLM).
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, WhatIfCard, AiCard, RelatedCard, SoWhat } from './ui';
import { computePrepayment, formatInr, formatInrShort } from '@/lib/finance';
import { type CalcConfig, getConfig, fmtValue, fmtPreset, fmtUnit } from './registry';
import { ResultActions, readUrlVals, useUrlSeed } from './actions';

function formatMonths(m: number): string {
  const months = Math.max(Math.round(m), 0);
  const y = Math.floor(months / 12);
  const mo = months % 12;
  if (y && mo) return `${y}y ${mo}m`;
  if (y) return `${y}y`;
  return `${mo}m`;
}

export function PrepaymentDetail({ config }: { config: CalcConfig }) {
  const initVals = React.useCallback(() => {
    const url = readUrlVals(config.inputs.map((i) => i.key));
    const o: Record<string, number> = {};
    config.inputs.forEach((inp) => {
      const v = url[inp.key];
      o[inp.key] = v !== undefined ? Math.min(Math.max(v, inp.min), inp.max) : inp.default;
    });
    return o;
  }, [config]);

  const [vals, setVals] = React.useState<Record<string, number>>(initVals);
  const resultRef = React.useRef<HTMLDivElement>(null);
  useUrlSeed(config.inputs, setVals);
  const principal = vals.loanAmount ?? 0;
  const ratePct = vals.loanRate ?? 0;
  const tenure = vals.tenure ?? 0;
  const oneTime = vals.oneTime ?? 0;
  const extraMonthly = vals.extraMonthly ?? 0;

  const base = { principal, annualRatePct: ratePct, years: tenure, oneTime, extraMonthly };
  const result = React.useMemo(
    () => computePrepayment({ principal, annualRatePct: ratePct, years: tenure, oneTime, extraMonthly }),
    [principal, ratePct, tenure, oneTime, extraMonthly],
  );
  const { emi, interestSaved, monthsSaved, newMonths, baselineMonths, newInterest, baselineInterest } = result;

  const savedWith = (patch: Partial<typeof base>) => computePrepayment({ ...base, ...patch }).interestSaved;
  const card = (name: string, val: string, saved: number) => {
    const d = saved - interestSaved;
    return { name, val, result: formatInrShort(saved), delta: `${formatInrShort(Math.abs(d))} ${d >= 0 ? 'more' : 'less'} saved`, up: d >= 0 };
  };
  const whatIf = [
    card('Prepay ₹1L more', formatInrShort(oneTime + 100000), savedWith({ oneTime: oneTime + 100000 })),
    card('Prepay ₹5L more', formatInrShort(oneTime + 500000), savedWith({ oneTime: oneTime + 500000 })),
    card('Pay ₹5,000/mo extra', `+${formatInrShort(extraMonthly + 5000)}/mo`, savedWith({ extraMonthly: extraMonthly + 5000 })),
  ];

  const monthsWithExtra5k = computePrepayment({ ...base, extraMonthly: extraMonthly + 5000 }).newMonths;
  const ai = [
    `**Prepaying ₹1L more** now would save about **${formatInr(savedWith({ oneTime: oneTime + 100000 }) - interestSaved)}** more in interest — prepayments early in the loan save the most.`,
    `**Paying ₹5,000 more each month** would clear the loan about **${formatMonths(Math.max(newMonths - monthsWithExtra5k, 0))}** sooner than your current plan.`,
    `Your prepayment cuts the term from **${formatMonths(baselineMonths)}** to **${formatMonths(newMonths)}** and saves **${formatInr(interestSaved)}** in interest, with the EMI staying at ${formatInrShort(emi)}/mo.`,
  ];

  const reset = () => setVals(initVals());
  const setKey = (k: string, v: number) => setVals((s) => ({ ...s, [k]: v }));
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* INPUT PANEL */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Loan & Prepayment</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the sliders — the savings update instantly.</p>

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
            unit={fmtUnit(inp.fmt)}
          />
        ))}

        <div className="flex gap-2">
          <Btn variant="pri" className="flex-1">Calculate</Btn>
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={vals} name={config.name} targetRef={resultRef} />
        </div>
      </Panel>

      {/* RESULT PANEL */}
      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi hero label="Interest Saved" value={formatInr(interestSaved)} sub={`EMI stays at ${formatInrShort(emi)}/mo`} />
          <Kpi label="Time Saved" value={formatMonths(monthsSaved)} sub="Loan clears sooner" accent="pos" />
          <Kpi label="New Loan Term" value={formatMonths(newMonths)} sub={`Was ${formatMonths(baselineMonths)}`} />
          <Kpi label="Total Interest Now" value={formatInr(newInterest)} sub={`Was ${formatInrShort(baselineInterest)}`} />
        </div>

        {/* Before vs after */}
        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Before vs After Prepaying" />
          <Panel>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-xl border border-line p-3.5">
                <div className="text-caption font-semibold uppercase tracking-[0.04em] text-ink-muted">Without prepayment</div>
                <div className="mt-2 text-small text-ink">Term: <b className="font-semibold">{formatMonths(baselineMonths)}</b></div>
                <div className="mt-1 text-small text-ink">Interest: <b className="font-mono font-semibold">{formatInr(baselineInterest)}</b></div>
              </div>
              <div className="rounded-xl border border-emerald/30 bg-emerald/[0.06] p-3.5">
                <div className="text-caption font-semibold uppercase tracking-[0.04em] text-emerald">With prepayment</div>
                <div className="mt-2 text-small text-ink">Term: <b className="font-semibold">{formatMonths(newMonths)}</b></div>
                <div className="mt-1 text-small text-ink">Interest: <b className="font-mono font-semibold">{formatInr(newInterest)}</b></div>
              </div>
            </div>
            <SoWhat>
              Prepaying saves <b className="font-semibold text-ink">{formatInr(interestSaved)}</b> in interest and clears the loan <b className="font-semibold text-ink">{formatMonths(monthsSaved)}</b> sooner. Early prepayments save the most, since more of each early EMI is interest.
            </SoWhat>
          </Panel>
        </Section>

        {/* What if */}
        <Section className="mt-[18px]">
          <SectionHeader index="✦" title="What If…" info="More prepayment, more saved" />
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
            <DisclosureBundle notAdvice="For education only — not financial advice. These figures illustrate how prepayment changes your own loan; they are not a recommendation. Check your lender's prepayment terms and any charges before acting." />
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
        <div data-no-export="true" className="fixed bottom-[18px] left-1/2 z-[55] flex -translate-x-1/2 items-center gap-3.5 rounded-2xl bg-navy/95 px-4 py-3 shadow-[0_24px_60px_-20px_rgba(15,23,42,.45)] backdrop-blur">
          <div className="text-white">
            <small className="block text-[10px] font-semibold uppercase tracking-[0.04em] text-slate-400">Interest Saved</small>
            <span className="text-small font-bold">{formatInrShort(interestSaved)}</span>
          </div>
          <Btn variant="pri" className="px-3.5">Calculate</Btn>
        </div>
      </div>
    </div>
  );
}

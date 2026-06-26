'use client';

/**
 * SwpDetail — config-driven 'swp' view (E3 decumulation). A corpus earns a return
 * while a monthly amount (optionally inflation-indexed) is withdrawn: how long it
 * lasts, total withdrawn, and whether it is sustainable. Uses computeSwp.
 *
 * COMPLIANCE: the figures are the user's own; no advice; disclaimer beside result.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeSwp, formatInr, formatInrShort } from '@/lib/finance';
import { type CalcConfig, getConfig, fmtValue, fmtPreset, fmtUnit } from './registry';
import { ResultActions, readUrlVals, useUrlSeed, type ExcelTable } from './actions';

function fmtMonths(m: number): string {
  const y = Math.floor(m / 12);
  const mo = m % 12;
  if (y && mo) return `${y}y ${mo}m`;
  if (y) return `${y}y`;
  return `${mo}m`;
}

export function SwpDetail({ config }: { config: CalcConfig }) {
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

  const corpus = vals.corpus ?? 0;
  const monthlyWithdrawal = vals.monthlyWithdrawal ?? 0;
  const rate = vals.rate ?? 0;
  const inflation = vals.inflation ?? 0;

  const result = React.useMemo(
    () => computeSwp({ corpus, monthlyWithdrawal, annualRatePct: rate, inflationPct: inflation }),
    [corpus, monthlyWithdrawal, rate, inflation],
  );
  const { monthsLasted, sustainable, totalWithdrawn } = result;
  const lastsLabel = sustainable ? '60+ yrs' : fmtMonths(monthsLasted);

  const reset = () => setVals(initVals());
  const setKey = (k: string, v: number) => setVals((s) => ({ ...s, [k]: v }));
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const rows = result.series.filter((p) => p.year >= 1).map((p) => ({
    year: p.year,
    withdrawn: formatInrShort(p.withdrawn),
    balance: formatInrShort(p.balance),
  }));

  const excelTable: ExcelTable = {
    summary: `${config.name} — corpus ${formatInr(corpus)}, withdrawing ${formatInr(monthlyWithdrawal)}/mo at ${rate}% return${inflation ? `, rising ${inflation}%/yr` : ''}. ${sustainable ? 'Sustainable (lasts 60+ years).' : `Lasts about ${fmtMonths(monthsLasted)}.`}`,
    note: 'Educational illustration only — not investment advice. Assumes a constant annual return, which real markets do not provide; sequence-of-returns risk in a real drawdown can shorten how long the corpus lasts.',
    headers: ['Year', 'Total Withdrawn', 'Balance Left'],
    rows: result.series.filter((p) => p.year >= 1).map((p) => [p.year, Math.round(p.withdrawn), Math.round(p.balance)]),
    colFormats: ['num', 'inr', 'inr'],
  };

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* INPUT PANEL */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Withdrawal Plan</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the sliders — results update instantly.</p>

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
          <ResultActions vals={vals} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      {/* RESULT PANEL */}
      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi hero label="Your Corpus Lasts" value={lastsLabel} sub={`Withdrawing ${formatInrShort(monthlyWithdrawal)}/month`} />
          <Kpi label="Monthly Income" value={formatInr(monthlyWithdrawal)} sub="What you take out" />
          <Kpi label="Total Withdrawn" value={formatInr(totalWithdrawn)} sub={sustainable ? 'Over 60 years' : 'Until it runs out'} accent="pos" />
          <Kpi label="Status" value={sustainable ? 'Sustainable' : 'Will deplete'} sub={sustainable ? 'Withdrawals stay within growth' : 'Withdrawals exceed growth'} />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="How Long It Lasts" />
          <Panel>
            <SoWhat>
              {sustainable ? (
                <>Your withdrawals stay within what the corpus earns, so it could last <b className="font-semibold text-ink">indefinitely</b> at the assumed {rate}% return. Real returns vary year to year, so keep a buffer.</>
              ) : (
                <>At <b className="font-semibold text-ink">{formatInr(monthlyWithdrawal)}/month</b> the corpus runs out in about <b className="font-semibold text-ink">{fmtMonths(monthsLasted)}</b>. Withdrawing less, or earning more, makes it last longer — try the sliders.</>
              )}
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={`Withdrawing roughly the return keeps a corpus going — about **${formatInrShort((corpus * rate) / 100 / 12)}/month** at ${rate}% here leaves the principal untouched.`} />
            <AiCard text="**A real drawdown faces sequence risk** — a bad early stretch hurts more than the same returns later. Treat these as a guide and revisit yearly." />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. Assumes a constant annual return, which real markets do not provide; a poor early stretch can shorten how long the corpus lasts." />
          </div>
        </Section>

        <Section>
          <SectionHeader index="✦" title="Year-by-Year Balance" />
          <div className="max-h-[340px] overflow-auto rounded-[14px] border border-line">
            <table className="w-full border-collapse text-small">
              <thead>
                <tr>
                  {['Year', 'Total Withdrawn', 'Balance Left'].map((h, i) => (
                    <th key={h} className={`sticky top-0 z-[2] border-b-2 border-line bg-surface-2 px-3.5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-ink-muted ${i === 0 ? 'text-left' : 'text-right'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.year} className="hover:bg-surface-2">
                    <td className="border-b border-line px-3.5 py-2.5 text-left font-semibold text-ink">Year {r.year}</td>
                    <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-semibold text-ink-muted">{r.withdrawn}</td>
                    <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-bold text-ink">{r.balance}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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

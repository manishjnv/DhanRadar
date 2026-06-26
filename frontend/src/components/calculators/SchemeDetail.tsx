'use client';

/**
 * SchemeDetail — config-driven 'scheme' view (FD / RD / PPF). Picks the engine
 * from config.scheme; shows maturity / invested / interest, a growth chart, a
 * year-by-year table, and branded Excel export.
 *
 * COMPLIANCE: the figures are the user's own; no advice; disclaimer beside result.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, GrowthChart, AiCard, RelatedCard, SoWhat } from './ui';
import { computeFd, computeRd, computePpf, formatInr, formatInrShort } from '@/lib/finance';
import { type CalcConfig, getConfig, fmtValue, fmtPreset, fmtUnit } from './registry';
import { ResultActions, readUrlVals, useUrlSeed, type ExcelTable } from './actions';

export function SchemeDetail({ config }: { config: CalcConfig }) {
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

  const rate = vals.rate ?? 0;
  const years = vals.tenure ?? 0;
  const amount = config.scheme === 'fd' ? (vals.principal ?? 0) : config.scheme === 'rd' ? (vals.monthly ?? 0) : (vals.yearlyDeposit ?? 0);

  const result = React.useMemo(() => {
    if (config.scheme === 'fd') return computeFd(amount, rate, years, 4);
    if (config.scheme === 'rd') return computeRd(amount, rate, years);
    return computePpf(amount, rate, years);
  }, [config.scheme, amount, rate, years]);

  const { maturity, invested, interest } = result;
  const multiplier = invested > 0 ? maturity / invested : 0;

  const reset = () => setVals(initVals());
  const setKey = (k: string, v: number) => setVals((s) => ({ ...s, [k]: v }));
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const depositLabel = config.scheme === 'fd' ? `a one-time ${formatInr(amount)}` : config.scheme === 'rd' ? `${formatInr(amount)}/month` : `${formatInr(amount)}/year`;
  const excelTable: ExcelTable = {
    summary: `${config.name} — ${depositLabel} at ${rate}% for ${years} ${years === 1 ? 'year' : 'years'}. Maturity ${formatInr(maturity)} (invested ${formatInr(invested)}, interest ${formatInr(interest)}).`,
    note: `Educational illustration only — not investment advice.${config.scheme === 'ppf' ? ' PPF rate is government-notified and changes quarterly; PPF maturity is tax-free.' : ''}`,
    headers: ['Year', 'Invested', 'Value'],
    rows: result.series.filter((p) => p.year >= 1).map((p) => [p.year, Math.round(p.invested), Math.round(p.value)]),
    colFormats: ['num', 'inr', 'inr'],
  };

  const rows = result.series.filter((p) => p.year >= 1).map((p) => ({
    year: p.year,
    invested: formatInrShort(p.invested),
    value: formatInrShort(p.value),
    interest: `+${formatInrShort(Math.max(p.value - p.invested, 0))}`,
  }));

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* INPUT PANEL */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Deposit</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the sliders — the maturity updates instantly.</p>

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
          <Kpi hero label="Maturity Value" value={formatInr(maturity)} sub={`From ${depositLabel} over ${years} ${years === 1 ? 'year' : 'years'}`} />
          <Kpi label="You Invest" value={formatInr(invested)} sub="Total deposited" />
          <Kpi label="Interest Earned" value={formatInr(interest)} sub="Growth on your money" accent="pos" />
          <Kpi label="Growth Multiple" value={`${multiplier.toFixed(2)}×`} sub="Maturity ÷ invested" />
        </div>

        <Panel className="mt-3.5">
          <div className="mb-1.5 flex items-center justify-between">
            <div className="text-small font-medium text-ink">Growth Over Time</div>
            <div className="text-caption tracking-normal text-ink-muted">Invested vs Value</div>
          </div>
          <GrowthChart series={result.series} />
        </Panel>

        <Section className="mt-[18px]">
          <SectionHeader index="✦" title="What This Shows" />
          <Panel>
            <SoWhat>
              {config.scheme === 'ppf'
                ? <>PPF compounds <b className="font-semibold text-ink">once a year</b> at the notified rate and is <b className="font-semibold text-ink">tax-free</b> (EEE). The rate is set by the government and can change each quarter.</>
                : config.scheme === 'fd'
                  ? <>An FD compounds <b className="font-semibold text-ink">quarterly</b>. Interest is taxable at your slab rate, so your post-tax return is lower than the headline rate.</>
                  : <>An RD takes a fixed monthly deposit and compounds <b className="font-semibold text-ink">quarterly</b>. Interest is taxable at your slab.</>}
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={`You'd deposit **${formatInr(invested)}** and receive **${formatInr(maturity)}** — about **${formatInr(interest)}** in interest at ${rate}%.`} />
            <AiCard text={config.scheme === 'ppf' ? '**PPF interest is tax-free**, which often makes its effective return higher than a taxable FD at the same rate.' : '**Compare the post-tax return** with a debt fund or PPF — the headline rate is before tax for FD/RD.'} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. Bank/Post-Office rates and compounding conventions vary; confirm with your provider." />
          </div>
        </Section>

        <Section>
          <SectionHeader index="✦" title="Year-by-Year Growth" />
          <div className="max-h-[340px] overflow-auto rounded-[14px] border border-line">
            <table className="w-full border-collapse text-small">
              <thead>
                <tr>
                  {['Year', 'Invested', 'Value', 'Interest'].map((h, i) => (
                    <th key={h} className={`sticky top-0 z-[2] border-b-2 border-line bg-surface-2 px-3.5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-ink-muted ${i === 0 ? 'text-left' : 'text-right'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.year} className="hover:bg-surface-2">
                    <td className="border-b border-line px-3.5 py-2.5 text-left font-semibold text-ink">Year {r.year}</td>
                    <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-semibold text-ink-muted">{r.invested}</td>
                    <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-bold text-ink">{r.value}</td>
                    <td className="border-b border-line px-3.5 py-2.5 text-right font-mono font-semibold text-emerald">{r.interest}</td>
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

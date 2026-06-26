'use client';

/**
 * RateDetail — config-driven 'rate' view (E5). Computes a CAGR from a start and
 * end value over a period (and, for Fund Return, a current value from an amount).
 *
 * COMPLIANCE: the figures are the user's own computed numbers; no advisory verbs;
 * disclaimer beside the result; share/download of the user's own figures.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeCagr, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig, fmtValue, fmtPreset, fmtUnit } from './registry';
import { ResultActions, readUrlVals, useUrlSeed } from './actions';

export function RateDetail({ config }: { config: CalcConfig }) {
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

  const map = config.rateMap ?? { begin: 'beginValue', end: 'endValue' };
  const begin = vals[map.begin] ?? 0;
  const end = vals[map.end] ?? 0;
  const years = vals.years ?? 0;
  const result = React.useMemo(() => computeCagr(begin, end, years), [begin, end, years]);
  const amount = map.amount ? vals[map.amount] ?? 0 : 0;
  const currentValue = map.amount && begin > 0 ? (amount * end) / begin : 0;
  const gain = currentValue - amount;

  const reset = () => setVals(initVals());
  const setKey = (k: string, v: number) => setVals((s) => ({ ...s, [k]: v }));
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* INPUT PANEL */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Numbers</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the sliders — the rate updates instantly.</p>

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
          <Kpi hero label="Annual Growth (CAGR)" value={`${result.cagrPct.toFixed(2)}%`} sub="Smoothed yearly growth rate" />
          <Kpi label="Total Return" value={`${result.absolutePct.toFixed(1)}%`} sub="Point-to-point, not annualised" accent="pos" />
          <Kpi label="Doubles Every" value={result.doublingYears > 0 ? `${result.doublingYears.toFixed(1)} yrs` : '—'} sub="At this growth rate" />
          {map.amount && <Kpi label="Current Value" value={formatInr(currentValue)} sub={`Gain ${formatInr(Math.max(gain, 0))}`} />}
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="What This Means" />
          <Panel>
            <SoWhat>
              A <b className="font-semibold text-ink">{result.cagrPct.toFixed(2)}%</b> CAGR means the value grew as if it rose that much <em>every</em> year — a smoothed rate, not what any single year did. Over the period the total change was <b className="font-semibold text-ink">{result.absolutePct.toFixed(1)}%</b>.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={`**CAGR smooths out the bumps** — your value changed **${result.absolutePct.toFixed(1)}%** in total, which works out to **${result.cagrPct.toFixed(2)}% a year** compounded.`} />
            <AiCard text={result.doublingYears > 0 ? `At **${result.cagrPct.toFixed(2)}%** a year, money **doubles in about ${result.doublingYears.toFixed(1)} years** (the Rule of 72 in action).` : 'With no growth, the value never doubles — try a higher ending value.'} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. CAGR describes past growth of the numbers you entered; it does not predict future returns. Past performance does not indicate future results." />
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

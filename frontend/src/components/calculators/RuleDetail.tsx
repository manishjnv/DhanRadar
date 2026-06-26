'use client';

/**
 * RuleDetail — config-driven 'rule' view (E5). The Rule of 72 / 114 / 144: how
 * long money takes to double, triple, and quadruple at a given rate.
 *
 * COMPLIANCE: arithmetic on the user's own assumed rate; no advice; disclaimer.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { ruleOf } from '@/lib/finance';
import { type CalcConfig, getConfig, fmtValue, fmtPreset, fmtUnit } from './registry';
import { ResultActions, readUrlVals, useUrlSeed } from './actions';

export function RuleDetail({ config }: { config: CalcConfig }) {
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
  const result = React.useMemo(() => ruleOf(rate), [rate]);
  const fmtYrs = (n: number) => (n > 0 ? `${n.toFixed(1)} yrs` : '—');

  const reset = () => setVals(initVals());
  const setKey = (k: string, v: number) => setVals((s) => ({ ...s, [k]: v }));
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* INPUT PANEL */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Rate</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the slider — the times update instantly.</p>

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
          <Kpi hero label="Doubles In" value={fmtYrs(result.double)} sub={`At ${rate}% a year (Rule of 72)`} />
          <Kpi label="Triples In" value={fmtYrs(result.triple)} sub="Rule of 114" />
          <Kpi label="Quadruples In" value={fmtYrs(result.quad)} sub="Rule of 144" />
          <Kpi label="Exact Doubling" value={fmtYrs(result.exactDouble)} sub="Precise (ln 2 / ln(1+r))" accent="pos" />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="How the Rule Works" />
          <Panel>
            <SoWhat>
              Divide <b className="font-semibold text-ink">72</b> by the rate for a quick doubling time. At {rate}% that is <b className="font-semibold text-ink">{fmtYrs(result.double)}</b> — close to the exact <b className="font-semibold text-ink">{fmtYrs(result.exactDouble)}</b>. The rule is a handy shortcut, accurate enough for rates in the usual 4–15% range.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={`At **${rate}% a year**, money roughly **doubles in ${fmtYrs(result.double)}**, triples in ${fmtYrs(result.triple)}, and quadruples in ${fmtYrs(result.quad)}.`} />
            <AiCard text="**Small rate changes compound** — even 2% more a year noticeably shortens the doubling time. Slide the rate to see how much." />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. These are arithmetic doubling times at the rate you assumed; real returns vary and are not guaranteed." />
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

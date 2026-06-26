'use client';

/**
 * StpDetail — 'stp' view: Systematic Transfer Plan. A lump in a source fund
 * (often debt) drains gradually into a target fund month by month. Uses
 * computeStp from @/lib/finance/transfer.
 *
 * COMPLIANCE: an educational ESTIMATE on the user's own assumptions — not
 * investment advice. Returns are the user's own figures, not predictions.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeStp, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

export function StpDetail({ config }: { config: CalcConfig }) {
  const [sourceCorpus, setSourceCorpus] = React.useState(1_000_000);
  const [monthlyTransfer, setMonthlyTransfer] = React.useState(25_000);
  const [sourceRate, setSourceRate] = React.useState(6);
  const [targetRate, setTargetRate] = React.useState(12);
  const [years, setYears] = React.useState(5);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(
    () =>
      computeStp({
        sourceCorpus,
        monthlyTransfer,
        sourceRatePct: sourceRate,
        targetRatePct: targetRate,
        years,
      }),
    [sourceCorpus, monthlyTransfer, sourceRate, targetRate, years],
  );

  const reset = () => {
    setSourceCorpus(1_000_000);
    setMonthlyTransfer(25_000);
    setSourceRate(6);
    setTargetRate(12);
    setYears(5);
  };

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const drainLabel = r.monthsToDrain > 0 ? `${r.monthsToDrain} mo` : 'Lasts the period';
  const drainSub = r.monthsToDrain > 0 ? 'Source fully moved to target' : 'Source not fully drained';

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${formatInr(sourceCorpus)} source at ${sourceRate}% → ${formatInr(monthlyTransfer)}/mo into target at ${targetRate}% for ${years} yr${years === 1 ? '' : 's'}: target built ${formatInr(r.targetBuilt)}, source left ${formatInr(r.sourceLeft)}, combined ${formatInr(r.combined)}.`,
    note: `Educational estimate only — not investment advice. Returns (${sourceRate}% source, ${targetRate}% target) are your own assumptions, not predictions; real markets vary.`,
    headers: ['Item', 'Amount'],
    rows: [
      ['Source corpus', Math.round(sourceCorpus)],
      ['Total transferred', Math.round(r.totalTransferred)],
      ['Target built', Math.round(r.targetBuilt)],
      ['Source left', Math.round(r.sourceLeft)],
      ['Combined value', Math.round(r.combined)],
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
        <h3 className="m-0 text-[15px] font-medium text-ink">Your STP Setup</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Transfer a fixed amount each month from a source into a target fund.</p>

        <RangeField
          label="Source Corpus"
          tip="The lump you start with in the source fund"
          value={sourceCorpus}
          min={100_000}
          max={100_000_000}
          step={10_000}
          format={formatInr}
          presets={[
            { label: '₹5L', value: 500_000 },
            { label: '₹10L', value: 1_000_000 },
            { label: '₹25L', value: 2_500_000 },
            { label: '₹50L', value: 5_000_000 },
          ]}
          onChange={setSourceCorpus}
          unit="₹"
        />

        <RangeField
          label="Monthly Transfer"
          tip="Moved into the target fund each month"
          value={monthlyTransfer}
          min={1_000}
          max={1_000_000}
          step={1_000}
          format={formatInr}
          presets={[
            { label: '₹10K', value: 10_000 },
            { label: '₹25K', value: 25_000 },
            { label: '₹50K', value: 50_000 },
            { label: '₹1L', value: 100_000 },
          ]}
          onChange={setMonthlyTransfer}
          unit="₹"
        />

        <RangeField
          label="Source Return (your assumption)"
          tip="Assumed return on the source (often a debt fund)"
          value={sourceRate}
          min={1}
          max={15}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[
            { label: '5%', value: 5 },
            { label: '6%', value: 6 },
            { label: '7%', value: 7 },
            { label: '8%', value: 8 },
          ]}
          onChange={setSourceRate}
          unit="%"
        />

        <RangeField
          label="Target Return (your assumption)"
          tip="Your assumption for the target fund — not a prediction"
          value={targetRate}
          min={1}
          max={30}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[
            { label: '8%', value: 8 },
            { label: '10%', value: 10 },
            { label: '12%', value: 12 },
            { label: '15%', value: 15 },
          ]}
          onChange={setTargetRate}
          unit="%"
        />

        <RangeField
          label="Duration"
          tip="How long the transfer runs"
          value={years}
          min={1}
          max={40}
          step={1}
          format={(n) => `${n} ${n === 1 ? 'yr' : 'yrs'}`}
          presets={[
            { label: '3 yrs', value: 3 },
            { label: '5 yrs', value: 5 },
            { label: '7 yrs', value: 7 },
            { label: '10 yrs', value: 10 },
          ]}
          onChange={setYears}
          unit="yrs"
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi hero label="Target Built" value={formatInr(r.targetBuilt)} sub="Grown at your target return" />
          <Kpi label="Source Left" value={formatInr(r.sourceLeft)} sub="Remaining in source fund" accent="pos" />
          <Kpi label="Combined Value" value={formatInr(r.combined)} sub="Source + target at end" />
          <Kpi label="Months to Drain" value={drainLabel} sub={drainSub} />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Breakdown" />
          <Panel>
            {row('Source corpus', formatInr(sourceCorpus))}
            {row('Total transferred out', formatInr(r.totalTransferred))}
            {row('Target built', formatInr(r.targetBuilt), true)}
            {row('Source left', formatInr(r.sourceLeft))}
            {row('Combined value', formatInr(r.combined), true)}
            <SoWhat>
              STP spreads a lump gradually into a higher-return fund to reduce timing risk — instead of investing everything at once, you move <b className="font-semibold text-ink">{formatInr(monthlyTransfer)}</b> a month while the source keeps earning at your assumed <b className="font-semibold text-ink">{sourceRate}%</b>.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={`**Your source earns ${sourceRate}% while draining** — so the money waiting to be transferred is not idle. Over ${years} yr${years === 1 ? '' : 's'} the source contributes ${formatInr(r.totalTransferred)} in transfers.`} />
            <AiCard text={`**Target builds to ${formatInr(r.targetBuilt)}** on your assumed ${targetRate}% return. These are your own figures — actual market returns vary and are not predictable.`} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. Returns are your own assumptions, not predictions; real markets vary." />
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

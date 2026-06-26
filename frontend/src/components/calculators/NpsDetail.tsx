'use client';

/**
 * NpsDetail — bespoke 'nps' view. Accumulate a monthly contribution to retirement
 * (via the SIP engine), then split the corpus: a tax-free lump (up to 60%) and an
 * annuity (≥40%) that buys a monthly pension.
 *
 * COMPLIANCE: the figures are the user's own assumptions; no advice; disclaimer.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeSip, formatInr, formatInrShort } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

const pct = (n: number) => `${n}%`;
const presetsOf = (vals: number[]) => vals.map((v) => ({ label: String(v), value: v }));
const inrPresets = (vals: number[]) => vals.map((v) => ({ label: formatInrShort(v), value: v }));

export function NpsDetail({ config }: { config: CalcConfig }) {
  const [monthly, setMonthly] = React.useState(10000);
  const [ret, setRet] = React.useState(10);
  const [currentAge, setCurrentAge] = React.useState(30);
  const [retireAge, setRetireAge] = React.useState(60);
  const [annuityPct, setAnnuityPct] = React.useState(40);
  const [annuityRate, setAnnuityRate] = React.useState(6);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const years = Math.max(retireAge - currentAge, 0);
  const corpus = React.useMemo(() => computeSip({ monthlySip: monthly, lumpSum: 0, years, annualRatePct: ret }).futureValue, [monthly, years, ret]);
  const lump = corpus * (1 - annuityPct / 100);
  const annuityCorpus = corpus * (annuityPct / 100);
  const pension = (annuityCorpus * annuityRate) / 100 / 12;
  const invested = monthly * years * 12;

  const reset = () => { setMonthly(10000); setRet(10); setCurrentAge(30); setRetireAge(60); setAnnuityPct(40); setAnnuityRate(6); };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${formatInr(monthly)}/mo for ${years} years at ${ret}%. Corpus at ${retireAge} ≈ ${formatInr(corpus)}; a ${annuityPct}% annuity at ${annuityRate}% gives ${formatInr(pension)}/month pension plus a ${formatInr(lump)} lump.`,
    note: 'Educational illustration only — not investment advice. Returns and the annuity rate are your own assumptions. At least 40% of the NPS corpus must buy an annuity; up to 60% can be withdrawn tax-free at 60.',
    headers: ['Item', 'Amount'],
    rows: [
      ['Total invested', Math.round(invested)],
      ['Corpus at retirement', Math.round(corpus)],
      [`Lump sum (${100 - annuityPct}%, tax-free)`, Math.round(lump)],
      [`Annuity corpus (${annuityPct}%)`, Math.round(annuityCorpus)],
      ['Monthly pension', Math.round(pension)],
    ],
    colFormats: ['text', 'inr'],
  };

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your NPS Plan</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Drag the sliders — results update instantly.</p>

        <RangeField label="Monthly Contribution" tip="How much you put in each month" value={monthly} min={500} max={200000} step={500} format={formatInr} presets={inrPresets([5000, 10000, 25000, 50000])} onChange={setMonthly} unit="₹" />
        <RangeField label="Expected Return" tip="Your assumption — not a DhanRadar prediction" value={ret} min={1} max={15} step={0.5} format={pct} presets={presetsOf([8, 10, 12])} onChange={setRet} unit="%" />
        <RangeField label="Current Age" tip="Your age today" value={currentAge} min={18} max={55} step={1} format={(n) => `${n}`} presets={presetsOf([25, 30, 35, 40])} onChange={setCurrentAge} />
        <RangeField label="Retirement Age" tip="When you exit NPS" value={retireAge} min={60} max={70} step={1} format={(n) => `${n}`} presets={presetsOf([60, 65, 70])} onChange={setRetireAge} />
        <RangeField label="Annuity Share" tip="At least 40% must buy a pension" value={annuityPct} min={40} max={100} step={5} format={pct} presets={presetsOf([40, 50, 60])} onChange={setAnnuityPct} unit="%" />
        <RangeField label="Annuity Rate" tip="The pension rate you assume" value={annuityRate} min={3} max={10} step={0.5} format={pct} presets={presetsOf([5, 6, 7])} onChange={setAnnuityRate} unit="%" />

        <div className="flex gap-2">
          <Btn variant="pri" className="flex-1">Calculate</Btn>
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi hero label={`Corpus at ${retireAge}`} value={formatInr(corpus)} sub={`From ${formatInrShort(monthly)}/month over ${years} years`} />
          <Kpi label="Monthly Pension" value={formatInr(pension)} sub={`${annuityPct}% annuity at ${annuityRate}%`} accent="pos" />
          <Kpi label="Tax-free Lump" value={formatInr(lump)} sub={`${100 - annuityPct}% taken at 60`} />
          <Kpi label="You Invest" value={formatInr(invested)} sub="Total contributions" />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="How NPS Pays Out" />
          <Panel>
            <SoWhat>
              At {retireAge} your corpus is about <b className="font-semibold text-ink">{formatInr(corpus)}</b>. You can take <b className="font-semibold text-ink">{formatInr(lump)}</b> tax-free and use the rest to buy a pension of roughly <b className="font-semibold text-ink">{formatInr(pension)}/month</b> — higher contributions or a longer horizon raise both.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={`Investing **${formatInrShort(monthly)}/month** for **${years} years** builds about **${formatInrShort(corpus)}** at your assumed ${ret}% return.`} />
            <AiCard text="**A bigger annuity share** raises the pension but lowers the tax-free lump — the split is your choice (40% minimum to annuity)." />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. NPS returns are market-linked; the return and annuity rate here are your own assumptions, not guarantees." />
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

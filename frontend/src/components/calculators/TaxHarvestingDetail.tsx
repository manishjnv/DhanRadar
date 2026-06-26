'use client';

/**
 * TaxHarvestingDetail — 'tax-harvesting' view: equity LTCG tax harvesting.
 * Each FY you can book up to ₹1.25 L of long-term equity gains tax-free and
 * re-buy (resetting your cost basis). Over years this beats letting the whole
 * gain accumulate and paying once. Uses computeTaxHarvesting.
 *
 * COMPLIANCE: educational estimate on the user's own figures — NOT tax advice.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeTaxHarvesting, TAX_CONFIG, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

export function TaxHarvestingDetail({ config }: { config: CalcConfig }) {
  const [annualGain, setAnnualGain] = React.useState(200000);
  const [years, setYears] = React.useState(10);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(
    () => computeTaxHarvesting({ annualGain, years }),
    [annualGain, years],
  );
  const reset = () => { setAnnualGain(200000); setYears(10); };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${formatInr(annualGain)}/yr over ${years} yr${years === 1 ? '' : 's'}: tax saved by harvesting ${formatInr(r.taxSaved)}.`,
    note: `Educational estimate only — not tax advice. LTCG @ ${TAX_CONFIG.equityLtcgPct}% + ${TAX_CONFIG.cessPct}% cess, exemption ₹${TAX_CONFIG.equityLtcgExemption.toLocaleString('en-IN')} (${TAX_CONFIG.asOf}). Assumes a steady annual gain; ignores transaction costs and timing.`,
    headers: ['Item', 'Amount'],
    rows: [
      ['Long-term gain per year', annualGain],
      ['Years', years],
      ['Yearly exemption', TAX_CONFIG.equityLtcgExemption],
      ['Tax if you harvest', Math.round(r.taxHarvesting)],
      ['Tax if realised at end', Math.round(r.taxStraight)],
      ['Tax saved', Math.round(r.taxSaved)],
    ],
    colFormats: ['text', 'inr'],
  };

  const row = (label: string, value: string, strong?: boolean) => (
    <div className="flex items-center justify-between border-b border-line py-2 last:border-b-0">
      <span className="text-small text-ink-secondary">{label}</span>
      <span className={`font-mono text-small ${strong ? 'font-bold text-ink' : 'font-semibold text-ink-secondary'}`}>{value}</span>
    </div>
  );

  const yrsLabel = (n: number) => `${n} ${n === 1 ? 'yr' : 'yrs'}`;

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Equity Gains</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          Book up to ₹1.25 L of long-term equity gains each year and re-buy — the tax you save adds up.
        </p>

        <RangeField
          label="Long-Term Gain per Year"
          tip="Equity gain you could book each year"
          value={annualGain}
          min={0}
          max={10000000}
          step={10000}
          format={formatInr}
          presets={[
            { label: '₹1L', value: 100000 },
            { label: '₹1.25L', value: 125000 },
            { label: '₹2L', value: 200000 },
            { label: '₹5L', value: 500000 },
          ]}
          onChange={setAnnualGain}
          unit="₹"
        />

        <RangeField
          label="Years"
          tip="Over how many years"
          value={years}
          min={1}
          max={30}
          step={1}
          format={yrsLabel}
          presets={[
            { label: '5 yrs', value: 5 },
            { label: '10 yrs', value: 10 },
            { label: '15 yrs', value: 15 },
            { label: '20 yrs', value: 20 },
          ]}
          onChange={setYears}
          unit="yrs"
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{ annualGain, years }} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Kpi hero label="Tax Saved" value={formatInr(r.taxSaved)} sub={`Over ${yrsLabel(years)} by harvesting`} />
          <Kpi label="Tax If You Harvest" value={formatInr(r.taxHarvesting)} sub="Booking the exemption yearly" />
          <Kpi label="Tax If You Don't" value={formatInr(r.taxStraight)} sub="Realising it all at the end" />
          <Kpi label="Yearly Exemption" value={formatInr(TAX_CONFIG.equityLtcgExemption)} sub="Tax-free LTCG each year" accent="pos" />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Breakdown" />
          <Panel>
            {row('Long-term gain per year', formatInr(annualGain))}
            {row('Years', yrsLabel(years))}
            {row('Yearly exemption', formatInr(TAX_CONFIG.equityLtcgExemption))}
            {row('Tax if harvested', formatInr(r.taxHarvesting))}
            {row('Tax if realised at end', formatInr(r.taxStraight))}
            {row('Tax saved', formatInr(r.taxSaved), true)}
            <SoWhat>
              Booking up to <b className="font-semibold text-ink">₹1.25 L</b> of long-term equity gains each financial year — and re-buying — uses the yearly exemption before it resets. Letting the whole gain build and realising it once means only one exemption offsets a much larger taxable amount.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {annualGain <= TAX_CONFIG.equityLtcgExemption ? (
              <AiCard text={`**Your entire yearly gain of ${formatInr(annualGain)} falls within the ₹1.25 L exemption** — so there is no LTCG tax to pay when you harvest annually. The tax saved versus a lump realisation comes entirely from using that one exemption every year instead of just once.`} />
            ) : (
              <AiCard text={`**Harvesting saves ${formatInr(r.taxSaved)} over ${yrsLabel(years)}** because each year you get a fresh ₹1.25 L exemption. Only the gain above the exemption (${formatInr(annualGain - TAX_CONFIG.equityLtcgExemption)}/yr) is taxed at ${TAX_CONFIG.equityLtcgPct}% + ${TAX_CONFIG.cessPct}% cess.`} />
            )}
            <AiCard text={`**Re-buying immediately after booking the gain** resets your cost basis, so future growth is tracked from the new price. There is no wash-sale rule in India for equity mutual funds — the timing flexibility is yours to use.`} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not tax advice. An estimate at FY 2025-26 rates; assumes a steady gain and ignores transaction costs and wash-sale-style timing. Consult a qualified professional." />
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

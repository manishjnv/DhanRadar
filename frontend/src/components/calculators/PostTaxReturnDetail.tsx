'use client';

/**
 * PostTaxReturnDetail — 'post-tax' view (E8): an investment grows at the user's
 * assumed return, then capital-gains tax is applied on redemption to show the
 * real take-home (net) value and the post-tax CAGR.
 *
 * COMPLIANCE: an educational ESTIMATE on the user's own figures — not tax or
 * investment advice. The return is the user's own assumption, not a prediction.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeSip, computeCapitalGainsTax, TAX_CONFIG, formatInr, type AssetType } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

const ASSETS: { value: AssetType; label: string }[] = [
  { value: 'equity', label: 'Equity / Equity MF (≥65% equity)' },
  { value: 'debt-new', label: 'Debt MF — bought on/after 1 Apr 2023' },
  { value: 'debt-old', label: 'Debt MF — bought before 1 Apr 2023' },
];
const SLABS = [5, 10, 15, 20, 30];

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <label className="mb-4 block">
      <span className="mb-1.5 block text-small font-semibold text-ink">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function PostTaxReturnDetail({ config }: { config: CalcConfig }) {
  const [amount, setAmount] = React.useState(100000);
  const [rate, setRate] = React.useState(12);
  const [years, setYears] = React.useState(5);
  const [assetType, setAssetType] = React.useState<AssetType>('equity');
  const [slabPct, setSlabPct] = React.useState(30);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(() => {
    const grossFv = computeSip({ monthlySip: 0, lumpSum: amount, years, annualRatePct: rate }).futureValue;
    const tax = computeCapitalGainsTax({ buyValue: amount, sellValue: grossFv, holdingMonths: years * 12, assetType, slabPct });
    const netFv = grossFv - tax.tax;
    const postTaxCagr = amount > 0 && years > 0 ? (Math.pow(netFv / amount, 1 / years) - 1) * 100 : 0;
    return { grossFv, tax, netFv, postTaxCagr: Number.isFinite(postTaxCagr) ? postTaxCagr : 0 };
  }, [amount, rate, years, assetType, slabPct]);

  const isDebt = assetType !== 'equity';
  const reset = () => { setAmount(100000); setRate(12); setYears(5); setAssetType('equity'); setSlabPct(30); };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${formatInr(amount)} at ${rate}% for ${years} yrs grows to ${formatInr(r.grossFv)} pre-tax; after ${formatInr(r.tax.tax)} tax, take-home ${formatInr(r.netFv)} (post-tax ${r.postTaxCagr.toFixed(1)}%).`,
    note: `Educational estimate only — not tax or investment advice. Tax at ${TAX_CONFIG.asOf} rates; the return is your own assumption, not a prediction.`,
    headers: ['Item', 'Amount'],
    rows: [
      ['Amount invested', Math.round(amount)],
      ['Pre-tax value', Math.round(r.grossFv)],
      ['Gain', Math.round(r.grossFv - amount)],
      ['Tax', Math.round(r.tax.tax)],
      ['Take-home value', Math.round(r.netFv)],
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
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Investment</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">See what you actually keep after capital-gains tax.</p>

        <Select label="Fund type" value={assetType} onChange={(v) => setAssetType(v as AssetType)} options={ASSETS} />
        <RangeField label="Amount Invested" tip="A one-time investment" value={amount} min={1000} max={100000000} step={1000} format={formatInr} presets={[{ label: '₹50K', value: 50000 }, { label: '₹1L', value: 100000 }, { label: '₹5L', value: 500000 }, { label: '₹10L', value: 1000000 }]} onChange={setAmount} unit="₹" />
        <RangeField label="Assumed Annual Return" tip="Your own assumption — not a DhanRadar prediction" value={rate} min={1} max={30} step={0.5} format={(n) => `${n}%`} presets={[{ label: '8%', value: 8 }, { label: '10%', value: 10 }, { label: '12%', value: 12 }, { label: '15%', value: 15 }]} onChange={setRate} unit="%" />
        <RangeField label="Holding Period" tip="How long you stay invested" value={years} min={1} max={40} step={1} format={(n) => `${n} ${n === 1 ? 'yr' : 'yrs'}`} presets={[{ label: '3y', value: 3 }, { label: '5y', value: 5 }, { label: '10y', value: 10 }, { label: '20y', value: 20 }]} onChange={setYears} unit="yrs" />
        {isDebt && <Select label="Your income-tax slab" value={String(slabPct)} onChange={(v) => setSlabPct(Number(v))} options={SLABS.map((s) => ({ value: String(s), label: `${s}%` }))} />}

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi hero label="Take-Home Value" value={formatInr(r.netFv)} sub={`After ${formatInr(r.tax.tax)} tax`} accent="pos" />
          <Kpi label="Pre-Tax Value" value={formatInr(r.grossFv)} sub={`From ${formatInr(amount)} over ${years} yrs`} />
          <Kpi label="Post-Tax Return" value={`${r.postTaxCagr.toFixed(1)}%`} sub={`vs ${rate}% pre-tax`} />
          <Kpi label="Tax Paid" value={formatInr(r.tax.tax)} sub={`${r.tax.term === 'short' ? 'Short-term' : 'Long-term'} · ${r.tax.ratePct}%`} />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Pre-Tax vs Take-Home" />
          <Panel>
            {row('Amount invested', formatInr(amount))}
            {row('Pre-tax value', formatInr(r.grossFv), true)}
            {row('Capital gain', formatInr(Math.max(r.grossFv - amount, 0)))}
            {r.tax.exemptionUsed > 0 && row('₹1.25 L LTCG exemption used', `− ${formatInr(r.tax.exemptionUsed)}`)}
            {row(`Tax @ ${r.tax.ratePct}% + ${TAX_CONFIG.cessPct}% cess`, formatInr(r.tax.tax))}
            {row('Take-home value', formatInr(r.netFv), true)}
            <SoWhat>
              Tax takes about <b className="font-semibold text-ink">{(r.grossFv > amount ? (r.tax.tax / (r.grossFv - amount)) * 100 : 0).toFixed(0)}%</b> of your gain here, so your {rate}% assumed return works out to roughly <b className="font-semibold text-ink">{r.postTaxCagr.toFixed(1)}%</b> after tax.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={assetType === 'equity' ? '**Equity held over a year** is taxed at 12.5% (long-term) above the ₹1.25 L yearly exemption — far gentler than the 20% short-term rate.' : '**Debt funds bought after 1 Apr 2023** are taxed at your slab rate whatever the holding period, so the take-home gap is wider.'} />
            <AiCard text={`Your real, after-tax return here is about **${r.postTaxCagr.toFixed(1)}%**. Comparing funds on a post-tax basis is fairer than on headline returns alone.`} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice={`For education only — not tax or investment advice. An estimate at ${TAX_CONFIG.asOf} rates; surcharge and set-off rules are not modelled. The return is your own assumption. Consult a qualified professional.`} />
          </div>
        </Section>

        {related.length > 0 && (
          <Section>
            <SectionHeader index="✦" title="Related Calculators" />
            <div className="flex gap-3 overflow-x-auto pb-1 sm:grid sm:grid-cols-2 sm:overflow-visible lg:grid-cols-4">
              {related.map((c) => <RelatedCard key={c.slug} emoji={c.emoji} name={c.name} desc={c.sub} accent="royal" href={`/calculators/${c.slug}`} />)}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

'use client';

/**
 * TaxDetail — bespoke 'tax' view (E8): capital-gains tax on equity / debt MF with
 * asset-type and slab selects (not just sliders). Uses computeCapitalGainsTax.
 *
 * COMPLIANCE: an educational ESTIMATE on the user's own figures — explicitly not
 * tax advice; the disclaimer states the rate basis and to consult a professional.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeCapitalGainsTax, TAX_CONFIG, formatInr, type AssetType } from '@/lib/finance';
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
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function TaxDetail({ config }: { config: CalcConfig }) {
  const [buyValue, setBuyValue] = React.useState(100000);
  const [sellValue, setSellValue] = React.useState(300000);
  const [holdingMonths, setHoldingMonths] = React.useState(24);
  const [assetType, setAssetType] = React.useState<AssetType>('equity');
  const [slabPct, setSlabPct] = React.useState(30);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(
    () => computeCapitalGainsTax({ buyValue, sellValue, holdingMonths, assetType, slabPct }),
    [buyValue, sellValue, holdingMonths, assetType, slabPct],
  );
  const isDebt = assetType !== 'equity';
  const reset = () => { setBuyValue(100000); setSellValue(300000); setHoldingMonths(24); setAssetType('equity'); setSlabPct(30); };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const fmtMonths = (n: number) => `${Math.floor(n / 12)}y ${n % 12}m`;

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${ASSETS.find((a) => a.value === assetType)?.label}, held ${fmtMonths(holdingMonths)}. Gain ${formatInr(r.gain)} → ${r.term === 'short' ? 'STCG' : 'LTCG'} tax ${formatInr(r.tax)} (rate ${r.ratePct}% + ${TAX_CONFIG.cessPct}% cess).`,
    note: `Educational estimate only — not tax advice. Rates as of ${TAX_CONFIG.asOf}; surcharge (income-dependent) is not included. Consult a qualified professional for your actual liability.`,
    headers: ['Item', 'Amount'],
    rows: [
      ['Sale value', Math.round(sellValue)],
      ['Cost', Math.round(buyValue)],
      ['Capital gain', Math.round(r.gain)],
      ['Exemption used', Math.round(r.exemptionUsed)],
      ['Taxable gain', Math.round(r.taxableGain)],
      [`Tax @ ${r.ratePct}%`, Math.round(r.baseTax)],
      [`Cess @ ${TAX_CONFIG.cessPct}%`, Math.round(r.cess)],
      ['Total tax', Math.round(r.tax)],
      ['Post-tax value', Math.round(r.postTaxValue)],
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
      {/* INPUT PANEL */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Sale</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Enter what you paid, what you sold for, and how long you held it.</p>

        <Select label="Fund type" value={assetType} onChange={(v) => setAssetType(v as AssetType)} options={ASSETS} />
        <RangeField label="Cost (what you paid)" tip="Your purchase value" value={buyValue} min={1000} max={100000000} step={1000} format={formatInr} presets={[{ label: '₹50K', value: 50000 }, { label: '₹1L', value: 100000 }, { label: '₹5L', value: 500000 }, { label: '₹10L', value: 1000000 }]} onChange={setBuyValue} unit="₹" />
        <RangeField label="Sale value" tip="What you sold (or current value) for" value={sellValue} min={1000} max={100000000} step={1000} format={formatInr} presets={[{ label: '₹1L', value: 100000 }, { label: '₹3L', value: 300000 }, { label: '₹5L', value: 500000 }, { label: '₹10L', value: 1000000 }]} onChange={setSellValue} unit="₹" />
        <RangeField label="Holding period" tip="How long you held it (months)" value={holdingMonths} min={1} max={120} step={1} format={fmtMonths} presets={[{ label: '6m', value: 6 }, { label: '1y', value: 12 }, { label: '2y', value: 24 }, { label: '3y', value: 36 }]} onChange={setHoldingMonths} />
        {isDebt && <Select label="Your income-tax slab" value={String(slabPct)} onChange={(v) => setSlabPct(Number(v))} options={SLABS.map((s) => ({ value: String(s), label: `${s}%` }))} />}

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      {/* RESULT PANEL */}
      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi hero label="Tax Payable" value={formatInr(r.tax)} sub={`${r.term === 'short' ? 'Short-term' : 'Long-term'} · ${r.ratePct}% + ${TAX_CONFIG.cessPct}% cess`} />
          <Kpi label="Post-Tax Value" value={formatInr(r.postTaxValue)} sub="Sale value minus tax" accent="pos" />
          <Kpi label="Effective Rate" value={`${r.effectivePct.toFixed(1)}%`} sub="Tax ÷ your gain" />
          <Kpi label="Your Gain" value={formatInr(Math.max(r.gain, 0))} sub={r.gain < 0 ? `Loss ${formatInr(-r.gain)} — no tax` : 'Capital gain'} />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Tax Breakdown" />
          <Panel>
            {row('Sale value', formatInr(sellValue))}
            {row('Cost', formatInr(buyValue))}
            {row('Capital gain', formatInr(r.gain), true)}
            {r.exemptionUsed > 0 && row('₹1.25 L LTCG exemption used', `− ${formatInr(r.exemptionUsed)}`)}
            {row('Taxable gain', formatInr(r.taxableGain))}
            {row(`Tax @ ${r.ratePct}%`, formatInr(r.baseTax))}
            {row(`Health & Education cess @ ${TAX_CONFIG.cessPct}%`, formatInr(r.cess))}
            {row('Total tax', formatInr(r.tax), true)}
            <SoWhat>
              {r.gain <= 0
                ? 'A loss has no tax — and may be set off against other capital gains (rules apply).'
                : `Held ${fmtMonths(holdingMonths)}, this is a ${r.term === 'short' ? 'short-term' : 'long-term'} gain taxed at ${r.ratePct}%${r.exemptionUsed > 0 ? ' after the ₹1.25 L equity LTCG exemption' : ''}.`}
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={assetType === 'equity' ? '**Holding equity past 12 months** moves the gain from 20% short-term to 12.5% long-term (above the ₹1.25 L yearly exemption) — a big difference.' : '**Debt funds bought after 1 Apr 2023** are taxed at your slab rate whatever the holding period — there is no long-term concession.'} />
            <AiCard text={`This is an estimate of **${formatInr(r.tax)}** at ${TAX_CONFIG.asOf} rates. Splitting a sale across two financial years can use the ₹1.25 L equity exemption twice — one of many planning ideas to discuss with a professional.`} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice={`For education only — not tax advice. An estimate at ${TAX_CONFIG.asOf} rates; surcharge (income-dependent) and set-off rules are not modelled. Consult a qualified tax professional for your actual liability.`} />
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

'use client';

/**
 * DividendTaxDetail — 'dividend' view (E8): mutual fund dividends (IDCW) are added
 * to your income and taxed at your slab rate; TDS @10% if over ₹5,000/yr. Uses
 * computeDividendTax.
 *
 * COMPLIANCE: an educational ESTIMATE on the user's own figures — not tax advice.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeDividendTax, DIVIDEND_CONFIG, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

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

export function DividendTaxDetail({ config }: { config: CalcConfig }) {
  const [dividend, setDividend] = React.useState(50000);
  const [slabPct, setSlabPct] = React.useState(30);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(() => computeDividendTax({ dividend, slabPct }), [dividend, slabPct]);
  const reset = () => { setDividend(50000); setSlabPct(30); };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${formatInr(dividend)} dividend at ${slabPct}% slab: tax ${formatInr(r.tax)}, take-home ${formatInr(r.netInHand)}${r.tds > 0 ? `, TDS ${formatInr(r.tds)} deducted at source` : ''}.`,
    note: `Educational estimate only — not tax advice. Dividends taxed at slab (${DIVIDEND_CONFIG.asOf}); TDS @${DIVIDEND_CONFIG.tdsPct}% over ₹${DIVIDEND_CONFIG.tdsThreshold}/yr is an advance, not extra tax.`,
    headers: ['Item', 'Amount'],
    rows: [
      ['Dividend received', Math.round(dividend)],
      [`Tax @ ${slabPct}% slab`, Math.round(r.tax)],
      ['Take-home', Math.round(r.netInHand)],
      ['TDS at source (advance)', Math.round(r.tds)],
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
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Dividend</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Dividends (IDCW) are added to your income and taxed at your slab.</p>

        <RangeField label="Dividend Received" tip="Total IDCW / dividend in the year" value={dividend} min={1000} max={10000000} step={1000} format={formatInr} presets={[{ label: '₹10K', value: 10000 }, { label: '₹50K', value: 50000 }, { label: '₹1L', value: 100000 }, { label: '₹5L', value: 500000 }]} onChange={setDividend} unit="₹" />
        <Select label="Your income-tax slab" value={String(slabPct)} onChange={(v) => setSlabPct(Number(v))} options={SLABS.map((s) => ({ value: String(s), label: `${s}%` }))} />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi hero label="Tax Payable" value={formatInr(r.tax)} sub={`${slabPct}% slab on ${formatInr(dividend)}`} />
          <Kpi label="Take-Home" value={formatInr(r.netInHand)} sub="Dividend minus tax" accent="pos" />
          <Kpi label="TDS at Source" value={formatInr(r.tds)} sub={r.tds > 0 ? `${DIVIDEND_CONFIG.tdsPct}% advance — adjusts in your return` : `None — under ₹${DIVIDEND_CONFIG.tdsThreshold}`} />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Breakdown" />
          <Panel>
            {row('Dividend received', formatInr(dividend))}
            {row(`Tax @ ${slabPct}% slab`, `− ${formatInr(r.tax)}`, true)}
            {row('Take-home', formatInr(r.netInHand), true)}
            {r.tds > 0 && row(`TDS @ ${DIVIDEND_CONFIG.tdsPct}% (advance, adjusts later)`, formatInr(r.tds))}
            <SoWhat>
              Dividends are taxed at your <b className="font-semibold text-ink">{slabPct}% slab</b>, so a higher slab means a bigger bite. Growth-option funds avoid this — gains are taxed only when you redeem.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text="**Dividends are fully taxed at your slab** — for someone in the 30% bracket that’s far steeper than the 12.5% long-term capital-gains rate on a growth fund." />
            <AiCard text={`**TDS of ${DIVIDEND_CONFIG.tdsPct}%** is cut at source once your yearly dividend crosses ₹${DIVIDEND_CONFIG.tdsThreshold}. It’s an advance you adjust against your final tax — not an extra charge.`} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice={`For education only — not tax advice. An estimate at ${DIVIDEND_CONFIG.asOf} rates; surcharge and other income are not modelled. Consult a qualified tax professional.`} />
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

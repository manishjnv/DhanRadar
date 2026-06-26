'use client';

/**
 * PortfolioTaxDetail — 'portfolio-tax' view: aggregate capital-gains tax across
 * several holdings, sharing ONE ₹1.25 L equity-LTCG exemption.
 *
 * COMPLIANCE: educational estimate on the user's own figures — not tax advice.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, AiCard, RelatedCard, SoWhat } from './ui';
import {
  computePortfolioTax,
  type Holding,
  type AssetType,
  TAX_CONFIG,
  formatInr,
} from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

const SLABS = [5, 10, 15, 20, 30];

const ASSET_OPTIONS: { value: AssetType; label: string }[] = [
  { value: 'equity',   label: 'Equity' },
  { value: 'debt-new', label: 'Debt post-Apr 2023' },
  { value: 'debt-old', label: 'Debt pre-Apr 2023' },
];

const DEFAULT: Holding[] = [
  { label: 'Equity Fund A', buyValue: 100000, sellValue: 180000, holdingMonths: 30, assetType: 'equity' },
  { label: 'Equity Fund B', buyValue: 200000, sellValue: 240000, holdingMonths: 8,  assetType: 'equity' },
  { label: 'Debt Fund',     buyValue: 300000, sellValue: 340000, holdingMonths: 40, assetType: 'debt-new' },
];

// ── inline Select (matches DividendTaxDetail pattern) ────────────────────────
function Select({ label, value, onChange, options }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
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

// ── shared breakdown row helper ───────────────────────────────────────────────
function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-line py-2 last:border-b-0">
      <span className="text-small text-ink-secondary">{label}</span>
      <span className={`font-mono text-small ${strong ? 'font-bold text-ink' : 'font-semibold text-ink-secondary'}`}>{value}</span>
    </div>
  );
}

// ── editable holdings table ───────────────────────────────────────────────────
function HoldingsTable({ rows, onSet, onAdd, onRemove }: {
  rows: Holding[];
  onSet: (i: number, patch: Partial<Holding>) => void;
  onAdd: () => void;
  onRemove: (i: number) => void;
}) {
  const inputCls = 'rounded-lg border border-line bg-surface px-2 py-1.5 text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40';
  const numCls   = `${inputCls} w-[90px] shrink-0 text-right font-mono [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none`;
  return (
    <div className="mb-4">
      <div className="mb-2 text-caption font-semibold uppercase tracking-[0.04em] text-royal">Holdings</div>
      <div className="space-y-2">
        {rows.map((h, i) => (
          <div key={i} className="grid gap-1.5 rounded-xl border border-line bg-surface-2 p-2.5">
            {/* name + remove */}
            <div className="flex items-center gap-1.5">
              <input
                value={h.label ?? ''}
                onChange={(e) => onSet(i, { label: e.target.value })}
                aria-label={`Holding ${i + 1} name`}
                placeholder="Name"
                className={`min-w-0 flex-1 ${inputCls}`}
              />
              <button
                type="button"
                onClick={() => onRemove(i)}
                aria-label={`Remove holding ${i + 1}`}
                className="shrink-0 rounded-md px-1.5 text-ink-muted hover:text-red focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
              >×</button>
            </div>
            {/* numeric inputs */}
            <div className="flex flex-wrap items-center gap-1.5">
              <div className="flex items-center gap-1 min-w-0">
                <span className="shrink-0 text-caption text-ink-muted">Buy ₹</span>
                <input
                  type="number"
                  value={h.buyValue}
                  step={10000}
                  min={0}
                  onChange={(e) => onSet(i, { buyValue: Number(e.target.value) || 0 })}
                  aria-label={`Holding ${i + 1} buy value`}
                  className={numCls}
                />
              </div>
              <div className="flex items-center gap-1 min-w-0">
                <span className="shrink-0 text-caption text-ink-muted">Sell ₹</span>
                <input
                  type="number"
                  value={h.sellValue}
                  step={10000}
                  min={0}
                  onChange={(e) => onSet(i, { sellValue: Number(e.target.value) || 0 })}
                  aria-label={`Holding ${i + 1} sell value`}
                  className={numCls}
                />
              </div>
              <div className="flex items-center gap-1 min-w-0">
                <span className="shrink-0 text-caption text-ink-muted">Mo.</span>
                <input
                  type="number"
                  value={h.holdingMonths}
                  step={1}
                  min={0}
                  onChange={(e) => onSet(i, { holdingMonths: Number(e.target.value) || 0 })}
                  aria-label={`Holding ${i + 1} holding months`}
                  className={`${inputCls} w-[52px] shrink-0 text-right font-mono [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none`}
                />
              </div>
            </div>
            {/* asset type */}
            <select
              value={h.assetType}
              onChange={(e) => onSet(i, { assetType: e.target.value as AssetType })}
              aria-label={`Holding ${i + 1} asset type`}
              className={`w-full ${inputCls}`}
            >
              {ASSET_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={onAdd}
        className="mt-2 w-full rounded-lg border border-dashed border-line py-1.5 text-caption font-semibold text-royal hover:border-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        + Add holding
      </button>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────
export function PortfolioTaxDetail({ config }: { config: CalcConfig }) {
  const [rows, setRows] = React.useState<Holding[]>(DEFAULT);
  const [slabPct, setSlabPct] = React.useState(30);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(() => computePortfolioTax(rows, slabPct), [rows, slabPct]);
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const onSet = (i: number, patch: Partial<Holding>) =>
    setRows((prev) => prev.map((h, idx) => (idx === i ? { ...h, ...patch } : h)));
  const onAdd = () =>
    setRows((prev) => [...prev, { label: 'New holding', buyValue: 100000, sellValue: 120000, holdingMonths: 15, assetType: 'equity' }]);
  const onRemove = (i: number) =>
    setRows((prev) => prev.length > 1 ? prev.filter((_, idx) => idx !== i) : prev);
  const reset = () => { setRows(DEFAULT); setSlabPct(30); };

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${rows.length} holdings, total gain ${formatInr(r.totalGain)}, total tax ${formatInr(r.totalTax)}, post-tax value ${formatInr(r.postTaxValue)}.`,
    note: `Educational estimate only — not tax advice. Rates at ${TAX_CONFIG.asOf}; surcharge and loss set-off rules are not modelled. Consult a qualified professional.`,
    headers: ['Holding', 'Gain', 'Term', 'Rate %', 'Tax'],
    rows: [
      ...rows.map((h, i): (string | number)[] => {
        const rr = r.rows[i];
        const termLabel = rr ? (rr.term === 'short' ? 'Short-term' : 'Long-term') : '';
        const gain = rr ? rr.gain : 0;
        const rate = rr ? rr.ratePct : 0;
        // per-row indicative tax (gain * rate / 100, pre-cess) — illustrative only
        const indicativeTax = gain > 0 ? Math.round((gain * rate) / 100) : 0;
        return [h.label ?? `Holding ${i + 1}`, Math.round(gain), termLabel, rate, indicativeTax];
      }),
      ['Total tax (incl. cess)', '', '', '', Math.round(r.totalTax)],
    ],
    colFormats: ['text', 'inr', 'text', 'pct', 'inr'],
  };

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* ── left panel ─────────────────────────────────────────────────────── */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Holdings</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          Edit the rows — tax updates instantly. The ₹1.25&nbsp;L LTCG exemption is shared across all your long-term equity gains.
        </p>

        <HoldingsTable rows={rows} onSet={onSet} onAdd={onAdd} onRemove={onRemove} />

        <Select
          label="Income-tax slab (for debt holdings)"
          value={String(slabPct)}
          onChange={(v) => setSlabPct(Number(v))}
          options={SLABS.map((s) => ({ value: String(s), label: `${s}%` }))}
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset to defaults" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      {/* ── right panel ────────────────────────────────────────────────────── */}
      <div ref={resultRef}>
        {/* KPI tiles */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            hero
            label="Total Tax"
            value={formatInr(r.totalTax)}
            sub={`Across ${rows.length} holding${rows.length === 1 ? '' : 's'}`}
          />
          <Kpi
            label="Post-Tax Value"
            value={formatInr(r.postTaxValue)}
            accent="pos"
            sub="After tax"
          />
          <Kpi
            label="Short-Term Tax"
            value={formatInr(r.stcgTax)}
            sub="Held ≤ 1 yr (equity)"
          />
          <Kpi
            label="Long-Term Tax"
            value={formatInr(r.ltcgTax)}
            sub={`After ${formatInr(r.exemptionUsed)} exemption`}
          />
        </div>

        {/* Per-holding breakdown */}
        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Holding-by-Holding Results" />
          <Panel>
            {rows.map((h, i) => {
              const rr = r.rows[i];
              if (!rr) return null;
              const termLabel = rr.term === 'short' ? 'Short-term' : 'Long-term';
              const gainStr = rr.gain >= 0
                ? `Gain ${formatInr(rr.gain)}`
                : `Loss ${formatInr(-rr.gain)}`;
              return (
                <div key={i} className="flex items-center justify-between border-b border-line py-2 last:border-b-0">
                  <div>
                    <span className="text-small font-semibold text-ink">{h.label || `Holding ${i + 1}`}</span>
                    <span className="ml-2 text-caption text-ink-muted">{termLabel} · {rr.ratePct}%</span>
                  </div>
                  <span className={`font-mono text-small font-semibold ${rr.gain >= 0 ? 'text-ink-secondary' : 'text-red'}`}>{gainStr}</span>
                </div>
              );
            })}
          </Panel>
        </Section>

        {/* Tax breakdown */}
        <Section>
          <SectionHeader index="✦" title="Tax Breakdown" />
          <Panel>
            <Row label="Total gain" value={formatInr(r.totalGain)} />
            <Row label="Short-term tax (incl. slab-taxed debt)" value={`${formatInr(r.stcgTax)}`} />
            <Row label="Long-term tax (after shared exemption)" value={`${formatInr(r.ltcgTax)}`} />
            <Row label={`Shared exemption used (of ₹${(TAX_CONFIG.equityLtcgExemption / 100000).toFixed(2)} L)`} value={formatInr(r.exemptionUsed)} />
            <Row label={`Health & education cess (${TAX_CONFIG.cessPct}%)`} value={formatInr(r.cess)} />
            <Row label="Total tax" value={formatInr(r.totalTax)} strong />
            <SoWhat>
              The ₹1.25&nbsp;L LTCG exemption is{' '}
              <b className="font-semibold text-ink">shared once</b> across all your
              long-term equity holdings — not granted per holding. If your combined
              long-term equity gain exceeds ₹1.25&nbsp;L, only the excess is taxed at 12.5%.
            </SoWhat>
          </Panel>
        </Section>

        {/* AI insights */}
        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={`**The shared ₹1.25 L exemption matters most when you have multiple long-term equity holdings.** If your total long-term equity gain is under ₹${(TAX_CONFIG.equityLtcgExemption / 100000).toFixed(2)} L, the LTCG tax across all of them is zero — regardless of how many funds you have.`} />
            <AiCard text="**Short-term equity gains are taxed at 20%** — nearly twice the 12.5% long-term rate. Holding equity for more than 12 months before redeeming moves the gain into the long-term bucket and the lower rate." />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice={`For education only — not tax advice. An estimate at ${TAX_CONFIG.asOf} rates; surcharge and loss set-off rules are not modelled. Consult a qualified professional.`} />
          </div>
        </Section>

        {/* Related calculators */}
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

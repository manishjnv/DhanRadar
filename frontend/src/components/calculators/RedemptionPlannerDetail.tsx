'use client';

/**
 * RedemptionPlannerDetail — 'redemption-planner' view. Editable lots table →
 * one illustrative tax-efficient redemption order (long-term equity first to
 * use the ₹1.25 L LTCG exemption before short-term). Uses computeRedemptionPlan.
 *
 * COMPLIANCE: shows ONE illustrative order — NOT a recommendation or advice.
 * Educational estimate at FY 2025-26 rates; consult a qualified professional.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeRedemptionPlan, TAX_CONFIG, formatInr, type Lot, type AssetType } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

// ── Slab select (mirrors DividendTaxDetail) ───────────────────────────────────
const SLABS = [5, 10, 15, 20, 30];

function SlabSelect({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <label className="mb-4 block">
      <span className="mb-1.5 block text-small font-semibold text-ink">Your income-tax slab</span>
      <select
        value={String(value)}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        {SLABS.map((s) => (
          <option key={s} value={String(s)}>{s}%</option>
        ))}
      </select>
    </label>
  );
}

// ── Default lots ──────────────────────────────────────────────────────────────
const DEFAULT_LOTS: Lot[] = [
  { label: 'Equity (long)', currentValue: 600000, cost: 400000, holdingMonths: 30, assetType: 'equity' },
  { label: 'Equity (short)', currentValue: 400000, cost: 300000, holdingMonths: 8, assetType: 'equity' },
  { label: 'Debt fund', currentValue: 500000, cost: 450000, holdingMonths: 40, assetType: 'debt-new' },
];

// ── Lots table (mirrors NetWorthDetail ItemList) ───────────────────────────────
function LotList({
  lots,
  onSet,
  onAdd,
  onRemove,
}: {
  lots: Lot[];
  onSet: (i: number, patch: Partial<Lot>) => void;
  onAdd: () => void;
  onRemove: (i: number) => void;
}) {
  return (
    <div className="mb-4">
      <div className="mb-2 text-caption font-semibold uppercase tracking-[0.04em] text-royal">Your Lots</div>

      {/* Column headers */}
      <div className="mb-1.5 flex items-center gap-1.5 px-0.5">
        <span className="flex-1 text-[10px] font-semibold uppercase tracking-[0.04em] text-ink-muted">Name</span>
        <span className="w-[80px] shrink-0 text-right text-[10px] font-semibold uppercase tracking-[0.04em] text-ink-muted">Value ₹</span>
        <span className="w-[80px] shrink-0 text-right text-[10px] font-semibold uppercase tracking-[0.04em] text-ink-muted">Cost ₹</span>
        <span className="w-[52px] shrink-0 text-right text-[10px] font-semibold uppercase tracking-[0.04em] text-ink-muted">Mo.</span>
        <span className="w-[84px] shrink-0 text-right text-[10px] font-semibold uppercase tracking-[0.04em] text-ink-muted">Type</span>
        <span className="w-5 shrink-0" />
      </div>

      <div className="space-y-1.5">
        {lots.map((lot, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <input
              value={lot.label ?? ''}
              onChange={(e) => onSet(i, { label: e.target.value })}
              aria-label={`Lot ${i + 1} name`}
              placeholder="Name"
              className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2 py-1.5 text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
            />
            <input
              type="number"
              value={lot.currentValue}
              step={10000}
              min={0}
              onChange={(e) => onSet(i, { currentValue: Number(e.target.value) || 0 })}
              aria-label={`Lot ${i + 1} current value`}
              className="w-[80px] shrink-0 rounded-lg border border-line bg-surface px-2 py-1.5 text-right font-mono text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
            />
            <input
              type="number"
              value={lot.cost}
              step={10000}
              min={0}
              onChange={(e) => onSet(i, { cost: Number(e.target.value) || 0 })}
              aria-label={`Lot ${i + 1} cost`}
              className="w-[80px] shrink-0 rounded-lg border border-line bg-surface px-2 py-1.5 text-right font-mono text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
            />
            <input
              type="number"
              value={lot.holdingMonths}
              step={1}
              min={0}
              onChange={(e) => onSet(i, { holdingMonths: Number(e.target.value) || 0 })}
              aria-label={`Lot ${i + 1} holding months`}
              className="w-[52px] shrink-0 rounded-lg border border-line bg-surface px-2 py-1.5 text-right font-mono text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
            />
            <select
              value={lot.assetType}
              onChange={(e) => onSet(i, { assetType: e.target.value as AssetType })}
              aria-label={`Lot ${i + 1} asset type`}
              className="w-[84px] shrink-0 rounded-lg border border-line bg-surface px-1.5 py-1.5 text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
            >
              <option value="equity">Equity</option>
              <option value="debt-new">Debt (new)</option>
              <option value="debt-old">Debt (old)</option>
            </select>
            <button
              type="button"
              onClick={() => onRemove(i)}
              aria-label={`Remove lot ${i + 1}`}
              className="w-5 shrink-0 rounded-md px-0.5 text-ink-muted hover:text-red focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={onAdd}
        className="mt-2 w-full rounded-lg border border-dashed border-line py-1.5 text-caption font-semibold text-royal hover:border-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        + Add lot
      </button>
    </div>
  );
}

// ── Step row in results ───────────────────────────────────────────────────────
function StepRow({ label, redeemValue, taxOnStep, term }: { label: string; redeemValue: number; taxOnStep: number; term: 'short' | 'long' }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line py-2.5 last:border-b-0">
      <div className="min-w-0 flex-1">
        <div className="truncate text-small font-semibold text-ink">{label}</div>
        <div className="mt-0.5 text-caption text-ink-muted">Tax on step: {formatInr(taxOnStep)}</div>
      </div>
      <div className="shrink-0 text-right">
        <div className="font-mono text-small font-bold text-ink">{formatInr(redeemValue)}</div>
        <span
          className={`mt-0.5 inline-block rounded px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.04em] ${
            term === 'long'
              ? 'bg-emerald/10 text-emerald'
              : 'bg-amber/10 text-amber'
          }`}
        >
          {term === 'long' ? 'Long-term' : 'Short-term'}
        </span>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export function RedemptionPlannerDetail({ config }: { config: CalcConfig }) {
  const [lots, setLots] = React.useState<Lot[]>(DEFAULT_LOTS);
  const [cashNeeded, setCashNeeded] = React.useState(500000);
  const [slabPct, setSlabPct] = React.useState(30);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(
    () => computeRedemptionPlan(lots, cashNeeded, slabPct),
    [lots, cashNeeded, slabPct],
  );

  const setLot = (i: number, patch: Partial<Lot>) =>
    setLots((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  const addLot = () =>
    setLots((prev) => [...prev, { label: 'New lot', currentValue: 100000, cost: 80000, holdingMonths: 13, assetType: 'equity' }]);
  const removeLot = (i: number) =>
    setLots((prev) => (prev.length > 1 ? prev.filter((_, idx) => idx !== i) : prev));
  const reset = () => { setLots(DEFAULT_LOTS); setCashNeeded(500000); setSlabPct(30); };

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — cash needed ${formatInr(cashNeeded)}: gross redeemed ${formatInr(r.totalRedeemed)}, tax ${formatInr(r.totalTax)}, net raised ${formatInr(r.netRaised)}${r.shortfall > 0 ? `, shortfall ${formatInr(r.shortfall)}` : ''}.`,
    note: `Educational illustration only — NOT advice. One illustrative tax-efficient redemption order at ${TAX_CONFIG.asOf} rates. LTCG exemption ₹${(TAX_CONFIG.equityLtcgExemption / 100000).toFixed(2)} L. Consult a qualified professional before redeeming.`,
    headers: ['Lot', 'Term', 'Amount Redeemed', 'Tax on Step'],
    rows: [
      ...r.steps.map((s): (string | number)[] => [s.label, s.term === 'long' ? 'Long-term' : 'Short-term', Math.round(s.redeemValue), Math.round(s.taxOnStep)]),
      ['Total', '', Math.round(r.totalRedeemed), Math.round(r.totalTax)],
      ['Net raised', '', Math.round(r.netRaised), 0],
      ['Exemption used', '', Math.round(r.exemptionUsed), 0],
      ...(r.shortfall > 0 ? [['Shortfall', '', Math.round(r.shortfall), 0] as (string | number)[]] : []),
    ],
    colFormats: ['text', 'text', 'inr', 'inr'],
  };

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* ── Left panel ─────────────────────────────────────────────────────── */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Lots &amp; Cash Need</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          Enter your lots below — the planner shows one illustrative tax-efficient order to raise the cash.
        </p>

        <RangeField
          label="Cash Needed"
          tip="How much cash you need to raise from these lots"
          value={cashNeeded}
          min={10000}
          max={100000000}
          step={10000}
          format={formatInr}
          presets={[
            { label: '₹2L', value: 200000 },
            { label: '₹5L', value: 500000 },
            { label: '₹10L', value: 1000000 },
            { label: '₹25L', value: 2500000 },
          ]}
          onChange={setCashNeeded}
          unit="₹"
        />

        <SlabSelect value={slabPct} onChange={setSlabPct} />

        <LotList lots={lots} onSet={setLot} onAdd={addLot} onRemove={removeLot} />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      {/* ── Right / results ────────────────────────────────────────────────── */}
      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            hero
            label="Tax on This Plan"
            value={formatInr(r.totalTax)}
            sub="For the cash you need"
          />
          <Kpi
            label="Net Raised"
            value={formatInr(r.netRaised)}
            sub={`Target ${formatInr(cashNeeded)}`}
            accent="pos"
          />
          <Kpi
            label="Gross Redeemed"
            value={formatInr(r.totalRedeemed)}
            sub="Total units sold"
          />
          <Kpi
            label="Exemption Used"
            value={formatInr(r.exemptionUsed)}
            sub={`₹1.25 L LTCG, tax-free`}
          />
        </div>

        {/* ── Suggested order ─────────────────────────────────────────────── */}
        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Suggested Redemption Order" />
          <Panel>
            {r.steps.length === 0 ? (
              <p className="text-small text-ink-muted">Add at least one lot with a positive value.</p>
            ) : (
              r.steps.map((step, i) => (
                <StepRow
                  key={i}
                  label={step.label}
                  redeemValue={step.redeemValue}
                  taxOnStep={step.taxOnStep}
                  term={step.term}
                />
              ))
            )}

            {r.shortfall > 0 && (
              <div className="mt-3 rounded-xl border border-amber/30 bg-amber/5 px-3.5 py-3 text-small text-ink-secondary">
                <b className="font-semibold text-ink">Shortfall:</b>{' '}
                The lots you entered can only raise {formatInr(r.netRaised)} net — still {formatInr(r.shortfall)} short of your {formatInr(cashNeeded)} target.
              </div>
            )}

            <SoWhat>
              This order redeems <b className="font-semibold text-ink">long-term equity first</b> to use the{' '}
              <b className="font-semibold text-ink">₹1.25&nbsp;L LTCG exemption</b> (tax-free) and the lower 12.5% rate,
              before moving to short-term lots taxed at the higher 20% rate. It is{' '}
              <b className="font-semibold text-ink">one illustrative tax-efficient order</b> — not a recommendation.
            </SoWhat>
          </Panel>
        </Section>

        {/* ── AI Insights ─────────────────────────────────────────────────── */}
        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={`**Long-term equity gains up to ₹1.25 L each financial year are tax-free.** Redeeming those lots first often means you raise the cash you need with little or no tax — the planner tries that order automatically.`} />
            <AiCard text="**Short-term equity gains are taxed at 20%** — nearly double the 12.5% long-term rate. If you can wait a few months for a short-term lot to cross 12 months, the tax saving can be meaningful. This illustration shows the order; timing is your call." />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice={`For education only — an illustration of one tax-efficient redemption order, NOT a recommendation or advice. An estimate at ${TAX_CONFIG.asOf} rates; surcharge and other income are not modelled. Consult a qualified professional before redeeming.`} />
          </div>
        </Section>

        {/* ── Related ─────────────────────────────────────────────────────── */}
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

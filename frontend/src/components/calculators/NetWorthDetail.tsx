'use client';

/**
 * NetWorthDetail — bespoke 'networth' view. Editable lists of assets and
 * liabilities → net worth (what you own minus what you owe). A snapshot, not a
 * projection.
 *
 * COMPLIANCE: the figures are the user's own; no advice; disclaimer.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, AiCard, RelatedCard, SoWhat } from './ui';
import { formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

type Item = { label: string; amount: number };

const DEFAULT_ASSETS: Item[] = [
  { label: 'Cash & bank', amount: 500000 },
  { label: 'Mutual funds', amount: 1500000 },
  { label: 'Stocks', amount: 500000 },
  { label: 'EPF / PPF', amount: 800000 },
  { label: 'Property', amount: 5000000 },
  { label: 'Gold', amount: 300000 },
];
const DEFAULT_LIABILITIES: Item[] = [
  { label: 'Home loan', amount: 3000000 },
  { label: 'Car loan', amount: 400000 },
  { label: 'Credit card', amount: 50000 },
];

function ItemList({ title, items, accent, onSet, onAdd, onRemove }: {
  title: string;
  items: Item[];
  accent: 'emerald' | 'red';
  onSet: (i: number, patch: Partial<Item>) => void;
  onAdd: () => void;
  onRemove: (i: number) => void;
}) {
  return (
    <div className="mb-4">
      <div className={`mb-2 text-caption font-semibold uppercase tracking-[0.04em] ${accent === 'emerald' ? 'text-emerald' : 'text-red'}`}>{title}</div>
      <div className="space-y-1.5">
        {items.map((it, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <input
              value={it.label}
              onChange={(e) => onSet(i, { label: e.target.value })}
              aria-label={`${title} ${i + 1} name`}
              className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2 py-1.5 text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
            />
            <input
              type="number"
              value={it.amount}
              step={10000}
              onChange={(e) => onSet(i, { amount: Number(e.target.value) || 0 })}
              aria-label={`${title} ${i + 1} amount`}
              className="w-[104px] shrink-0 rounded-lg border border-line bg-surface px-2 py-1.5 text-right font-mono text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
            />
            <button type="button" onClick={() => onRemove(i)} aria-label={`Remove ${title} ${i + 1}`} className="shrink-0 rounded-md px-1.5 text-ink-muted hover:text-red focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">×</button>
          </div>
        ))}
      </div>
      <button type="button" onClick={onAdd} className="mt-2 w-full rounded-lg border border-dashed border-line py-1.5 text-caption font-semibold text-royal hover:border-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">+ Add</button>
    </div>
  );
}

export function NetWorthDetail({ config }: { config: CalcConfig }) {
  const [assets, setAssets] = React.useState<Item[]>(DEFAULT_ASSETS);
  const [liabilities, setLiabilities] = React.useState<Item[]>(DEFAULT_LIABILITIES);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const sumA = assets.reduce((s, i) => s + (i.amount || 0), 0);
  const sumL = liabilities.reduce((s, i) => s + (i.amount || 0), 0);
  const net = sumA - sumL;
  const leverage = sumA > 0 ? Math.round((sumL / sumA) * 100) : 0;

  const setItem = (list: Item[], set: React.Dispatch<React.SetStateAction<Item[]>>) => (i: number, patch: Partial<Item>) => set(list.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  const addItem = (set: React.Dispatch<React.SetStateAction<Item[]>>) => () => set((s) => [...s, { label: 'New item', amount: 0 }]);
  const removeItem = (set: React.Dispatch<React.SetStateAction<Item[]>>) => (i: number) => set((s) => (s.length > 1 ? s.filter((_, idx) => idx !== i) : s));
  const reset = () => { setAssets(DEFAULT_ASSETS); setLiabilities(DEFAULT_LIABILITIES); };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — assets ${formatInr(sumA)} minus liabilities ${formatInr(sumL)} = net worth ${formatInr(net)}.`,
    note: 'Educational snapshot of the figures you entered — not investment or financial advice. Use current market values for the most accurate picture.',
    headers: ['Item', 'Type', 'Amount'],
    rows: [
      ...assets.map((a): (string | number)[] => [a.label, 'Asset', Math.round(a.amount)]),
      ...liabilities.map((l): (string | number)[] => [l.label, 'Liability', -Math.round(l.amount)]),
      ['Net worth', '', Math.round(net)],
    ],
    colFormats: ['text', 'text', 'inr'],
  };

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">What You Own & Owe</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Edit the rows — net worth updates instantly.</p>

        <ItemList title="Assets (own)" items={assets} accent="emerald" onSet={setItem(assets, setAssets)} onAdd={addItem(setAssets)} onRemove={removeItem(setAssets)} />
        <ItemList title="Liabilities (owe)" items={liabilities} accent="red" onSet={setItem(liabilities, setLiabilities)} onAdd={addItem(setLiabilities)} onRemove={removeItem(setLiabilities)} />

        <div className="flex gap-2">
          <Btn aria-label="Reset" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi hero label="Your Net Worth" value={formatInr(net)} sub="What you own minus what you owe" />
          <Kpi label="Total Assets" value={formatInr(sumA)} sub={`${assets.length} items`} accent="pos" />
          <Kpi label="Total Liabilities" value={formatInr(sumL)} sub={`${liabilities.length} items`} />
          <Kpi label="Leverage" value={`${leverage}%`} sub="Debt as % of assets" />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Where You Stand" />
          <Panel>
            <SoWhat>
              {net >= 0
                ? <>You own <b className="font-semibold text-ink">{formatInr(net)}</b> more than you owe. Debt is <b className="font-semibold text-ink">{leverage}%</b> of your assets — lower is generally safer.</>
                : <>You owe <b className="font-semibold text-ink">{formatInr(-net)}</b> more than you own right now. Reducing high-interest debt first usually helps the most.</>}
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text={`Your assets total **${formatInr(sumA)}** against **${formatInr(sumL)}** of liabilities — a net worth of **${formatInr(net)}**.`} />
            <AiCard text="**Track this over time** — a rising net worth, not just income, is the clearest sign of building wealth. Update it every few months." />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment or financial advice. This is a snapshot of the values you entered; use current market values for accuracy." />
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

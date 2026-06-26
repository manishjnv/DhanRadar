'use client';

/**
 * ExitLoadDetail — 'exit-load' view: the fee a fund charges if you redeem within
 * its exit-load window. Uses computeExitLoad.
 *
 * COMPLIANCE: an educational ESTIMATE on the user's own figures — not advice.
 * The actual load and window are set in each fund's Scheme Information Document.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeExitLoad, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

export function ExitLoadDetail({ config }: { config: CalcConfig }) {
  const [redeemValue, setRedeemValue] = React.useState(100000);
  const [loadPct, setLoadPct] = React.useState(1);
  const [holdingMonths, setHoldingMonths] = React.useState(6);
  const [windowMonths, setWindowMonths] = React.useState(12);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(
    () => computeExitLoad({ redeemValue, loadPct, holdingMonths, loadWindowMonths: windowMonths }),
    [redeemValue, loadPct, holdingMonths, windowMonths],
  );
  const reset = () => { setRedeemValue(100000); setLoadPct(1); setHoldingMonths(6); setWindowMonths(12); };
  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));
  const fmtMonths = (n: number) => `${Math.floor(n / 12)}y ${n % 12}m`;
  const monthsToWait = Math.max(windowMonths - holdingMonths, 0);

  const excelTable: ExcelTable = {
    summary: `${config.name} — redeeming ${formatInr(redeemValue)} after ${fmtMonths(holdingMonths)} with a ${loadPct}% load (window ${windowMonths} mo): ${r.applies ? `load ${formatInr(r.loadAmount)}, net ${formatInr(r.netValue)}` : 'no load — held past the window'}.`,
    note: 'Educational estimate only. The actual exit load and window are in each fund’s Scheme Information Document.',
    headers: ['Item', 'Amount'],
    rows: [
      ['Redemption value', Math.round(redeemValue)],
      [`Exit load @ ${loadPct}%`, Math.round(r.loadAmount)],
      ['Net you receive', Math.round(r.netValue)],
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
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Redemption</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">Check the fee for selling a fund before its exit-load window ends.</p>

        <RangeField label="Redemption Value" tip="How much you're redeeming" value={redeemValue} min={1000} max={100000000} step={1000} format={formatInr} presets={[{ label: '₹50K', value: 50000 }, { label: '₹1L', value: 100000 }, { label: '₹5L', value: 500000 }, { label: '₹10L', value: 1000000 }]} onChange={setRedeemValue} unit="₹" />
        <RangeField label="Exit Load" tip="The load %, from the fund's scheme document" value={loadPct} min={0} max={5} step={0.25} format={(n) => `${n}%`} presets={[{ label: '0.5%', value: 0.5 }, { label: '1%', value: 1 }, { label: '2%', value: 2 }]} onChange={setLoadPct} unit="%" />
        <RangeField label="Held For" tip="How long you've held the units" value={holdingMonths} min={0} max={60} step={1} format={fmtMonths} presets={[{ label: '3m', value: 3 }, { label: '6m', value: 6 }, { label: '1y', value: 12 }, { label: '2y', value: 24 }]} onChange={setHoldingMonths} />
        <RangeField label="Load Window" tip="Load applies if you redeem before this" value={windowMonths} min={1} max={60} step={1} format={fmtMonths} presets={[{ label: '6m', value: 6 }, { label: '1y', value: 12 }, { label: '2y', value: 24 }, { label: '3y', value: 36 }]} onChange={setWindowMonths} />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi hero label="Exit Load Fee" value={formatInr(r.loadAmount)} sub={r.applies ? `${loadPct}% of ${formatInr(redeemValue)}` : 'No load — held past the window'} />
          <Kpi label="Net You Receive" value={formatInr(r.netValue)} sub="After the load" accent="pos" />
          <Kpi label="Wait to Avoid" value={r.applies ? `${monthsToWait} mo` : 'None'} sub={r.applies ? 'Hold this much longer for ₹0 load' : 'You’re past the window'} />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Breakdown" />
          <Panel>
            {row('Redemption value', formatInr(redeemValue))}
            {row(`Exit load @ ${loadPct}%`, r.applies ? `− ${formatInr(r.loadAmount)}` : '₹0', true)}
            {row('Net you receive', formatInr(r.netValue), true)}
            <SoWhat>
              {r.applies
                ? <>You’re redeeming after <b className="font-semibold text-ink">{fmtMonths(holdingMonths)}</b>, inside the {fmtMonths(windowMonths)} window — waiting <b className="font-semibold text-ink">{monthsToWait} more month{monthsToWait === 1 ? '' : 's'}</b> would save the <b className="font-semibold text-ink">{formatInr(r.loadAmount)}</b> load.</>
                : <>You’ve held past the {fmtMonths(windowMonths)} window, so <b className="font-semibold text-ink">no exit load</b> applies.</>}
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text="**Exit load is separate from tax** — it’s a fund fee to discourage early exits, charged on the redemption value, not just the gain." />
            <AiCard text="**Most equity funds** use a 1% load for the first year. Always check the fund’s Scheme Information Document for the exact load and window." />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. The actual exit load and window are set by each fund and may differ from the values you enter." />
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

'use client';

/**
 * XirrDetail — bespoke 'xirr' view (E5). An editable cash-flow table (date +
 * amount rows; investments negative, returns positive) → the money-weighted
 * annualised return via the robust `computeXirr` (Newton + bisection).
 *
 * COMPLIANCE: figures are the user's own; no advice; disclaimer beside the result.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, AiCard, RelatedCard, SoWhat } from './ui';
import { computeXirr, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

type Flow = { date: string; amount: number }; // date as YYYY-MM-DD

const DEFAULT_FLOWS: Flow[] = [
  { date: '2023-01-01', amount: -50000 },
  { date: '2023-07-01', amount: -50000 },
  { date: '2024-01-01', amount: -50000 },
  { date: '2025-01-01', amount: 175000 },
];

export function XirrDetail({ config }: { config: CalcConfig }) {
  const [flows, setFlows] = React.useState<Flow[]>(DEFAULT_FLOWS);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const result = React.useMemo(() => {
    const parsed = flows.filter((f) => f.date).map((f) => ({ date: new Date(f.date), amount: f.amount }));
    return computeXirr(parsed);
  }, [flows]);

  const invested = flows.reduce((s, f) => s + (f.amount < 0 ? -f.amount : 0), 0);
  const received = flows.reduce((s, f) => s + (f.amount > 0 ? f.amount : 0), 0);
  const net = received - invested;

  const setFlow = (i: number, patch: Partial<Flow>) => setFlows((s) => s.map((f, idx) => (idx === i ? { ...f, ...patch } : f)));
  const addRow = () => setFlows((s) => [...s, { date: s[s.length - 1]?.date ?? '2024-01-01', amount: -10000 }]);
  const removeRow = (i: number) => setFlows((s) => (s.length > 2 ? s.filter((_, idx) => idx !== i) : s));
  const reset = () => setFlows(DEFAULT_FLOWS);

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${flows.length} cash flows. ${result.converged ? `XIRR ${result.xirrPct.toFixed(2)}%` : 'Not enough data to compute XIRR'}. Invested ${formatInr(invested)}, received ${formatInr(received)}.`,
    note: 'Educational illustration only — not investment advice. XIRR is the annualised return implied by your dated cash flows; it needs at least one investment (negative) and one return (positive).',
    headers: ['Date', 'Amount', 'Type'],
    rows: flows.map((f) => [f.date, Math.round(f.amount), f.amount < 0 ? 'Invested' : 'Received']),
    colFormats: ['text', 'inr', 'text'],
  };

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* INPUT PANEL — editable cash-flow table */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Cash Flows</h3>
        <p className="mb-3 mt-1 text-caption tracking-normal text-ink-muted">Money you invest is negative; money you get back is positive.</p>

        <div className="space-y-2">
          {flows.map((f, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <input
                type="date"
                value={f.date}
                onChange={(e) => setFlow(i, { date: e.target.value })}
                aria-label={`Cash flow ${i + 1} date`}
                className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2 py-1.5 text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
              />
              <input
                type="number"
                value={f.amount}
                step={1000}
                onChange={(e) => setFlow(i, { amount: Number(e.target.value) || 0 })}
                aria-label={`Cash flow ${i + 1} amount`}
                className="w-[96px] shrink-0 rounded-lg border border-line bg-surface px-2 py-1.5 text-right font-mono text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
              />
              <button type="button" onClick={() => removeRow(i)} aria-label={`Remove cash flow ${i + 1}`} className="shrink-0 rounded-md px-1.5 text-ink-muted hover:text-red focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">×</button>
            </div>
          ))}
        </div>

        <button type="button" onClick={addRow} className="mt-3 w-full rounded-lg border border-dashed border-line py-2 text-small font-semibold text-royal hover:border-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">+ Add a cash flow</button>

        <div className="mt-3.5 flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      {/* RESULT PANEL */}
      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi hero label="XIRR (Annualised Return)" value={result.converged ? `${result.xirrPct.toFixed(2)}%` : '—'} sub={result.converged ? 'Your true money-weighted return' : 'Add an investment and a return'} />
          <Kpi label="Total Invested" value={formatInr(invested)} sub="Sum of money put in" />
          <Kpi label="Total Received" value={formatInr(received)} sub="Sum of money taken out" />
          <Kpi label="Net Gain" value={formatInr(Math.max(net, 0))} sub={net < 0 ? `Loss ${formatInr(-net)}` : 'Received − invested'} accent="pos" />
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="What XIRR Tells You" />
          <Panel>
            <SoWhat>
              {result.converged ? (
                <>Your money earned <b className="font-semibold text-ink">{result.xirrPct.toFixed(2)}% a year</b>, accounting for <em>when</em> each amount went in or came out — the fair way to measure returns on SIPs, top-ups, and partial withdrawals.</>
              ) : (
                <>XIRR needs at least one <b className="font-semibold text-ink">investment</b> (negative) and one <b className="font-semibold text-ink">return</b> (positive). Add both to see your annualised return.</>
              )}
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text="**XIRR beats a simple return %** when you invest at different times — it weights each rupee by how long it was actually invested." />
            <AiCard text={result.converged ? `You put in **${formatInr(invested)}** and got back **${formatInr(received)}**, which works out to **${result.xirrPct.toFixed(2)}% a year**.` : 'Enter your real SIP dates and the final redemption to get your true return.'} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. XIRR is computed from the dated cash flows you entered; past returns do not predict future results." />
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

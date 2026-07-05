/**
 * Fund Detail V3 — sections D: Tax / Transactions / Alternatives / Similar / FAQ
 *
 * COMPLIANCE (non-negotiable #1, #2):
 *   - Alternatives and Similar render educational LABEL + confidence BAND via
 *     <FundScoreCell> — NEVER a 0–100 score number.
 *   - Returns %, expense %, ₹ tax amounts are factual → DOM-allowed.
 *   - No advisory verbs (buy/sell/hold/avoid/caution/switch) anywhere.
 *   - Transactions (P1) renders the owner's OWN real ledger rows from
 *     `GET /portfolio/{id}/transactions?isin=` — DOM-allowed user facts (§13).
 */
'use client';

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { FundAvatar } from '@/components/mf/explore/FundAvatar';
import { FundScoreCell } from '@/components/mf/explore/FundScoreCell';
import { useFundPeers } from '@/features/mf/api';
import { usePortfolioTransactions, type Transaction } from '@/features/portfolio/api';
import { DataState, type DataStatus } from '@/components/ui/DataState';
import { Skeleton } from '@/components/ui/Skeleton';
import { Panel, WhatThisMeans } from './parts';
import { TAX, FAQ } from './sampleData';
import type { Label } from '@/components/charts/ScoreRing';
import type { FundPeer } from '@/features/mf/types';


// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function inr(n: number): string {
  return '₹' + Math.round(n).toLocaleString('en-IN');
}

// Tone-tinted pill used for tag labels on alt/similar cards
const TAG_TINT: Record<string, string> = {
  emerald: 'bg-emerald/10 text-emerald border-emerald/20',
  royal:   'bg-royal/10  text-royal  border-royal/20',
  amber:   'bg-amber/10  text-amber  border-amber/20',
  cyan:    'bg-cyan/10   text-cyan   border-cyan/20',
};

// ─────────────────────────────────────────────────────────────────────────────
// S17 — TAX CENTER
// ─────────────────────────────────────────────────────────────────────────────

export function TaxSection({
  seedValue,
  costBasis,
}: {
  /** Signed-in owner's real current value for this fund (P1) — seeds the redemption slider. */
  seedValue?: number | null;
  /** Signed-in owner's real invested amount for this fund (P1) — the calculator's cost basis. */
  costBasis?: number | null;
} = {}) {
  const [amount, setAmount] = React.useState(
    seedValue != null && seedValue > 0 ? Math.round(seedValue) : TAX.defaultAmount,
  );
  // 1 = LTCG (> 1 year), 0 = STCG (< 1 year)
  const [holding, setHolding] = React.useState<0 | 1>(1);

  // Re-seed once the owner's real holding value resolves (it loads async, after this section
  // first mounts with the static sample default) — never overrides a value the user has since
  // dragged themselves.
  const seededRef = React.useRef(false);
  React.useEffect(() => {
    if (!seededRef.current && seedValue != null && seedValue > 0) {
      setAmount(Math.round(seedValue));
      seededRef.current = true;
    }
  }, [seedValue]);

  // Live computation — mirrors HTML JS lines 1131-1145. Cost basis is the owner's REAL invested
  // amount when signed in with this holding; the static sample figure otherwise (anonymous / no
  // CAS / not holding this fund) so the calculator still works with manual input.
  const cost    = costBasis != null && costBasis > 0 ? costBasis : TAX.costBasis;
  const gain    = Math.max(0, amount - cost);
  const isLT    = holding === 1;
  const exempt  = isLT ? Math.min(gain, TAX.ltcgExempt) : 0;
  const tax     = isLT
    ? Math.max(0, (gain - exempt) * TAX.ltcgRate)
    : gain * TAX.stcgRate;
  const net     = amount - tax;
  // The slider's static 50k-500k range is a sample-data assumption — widen the ceiling so a real
  // (signed-in) holding value larger than ₹5L is still reachable on the track.
  const sliderMax = Math.max(500000, Math.ceil(amount / 50000) * 50000);

  const holdingLabel = isLT ? '> 1 year (LTCG)' : '< 1 year (STCG)';
  const exemptLabel  = isLT ? `LTCG exemption (₹1.25L/yr)` : 'STCG exemption';
  const taxLabel     = isLT ? 'LTCG tax @ 12.5%' : 'STCG tax @ 20%';
  const exemptDisplay = isLT ? `−${inr(exempt)}` : '₹0';

  return (
    <Panel className="p-5 sm:p-6">
      {/* 2-col on sm+, 1-col on mobile */}
      <div className="grid gap-6 sm:grid-cols-2">

        {/* LEFT — calculator controls */}
        <div>
          <p className="mb-4 text-small font-bold text-ink">Tax calculator</p>

          {/* Redemption amount slider */}
          <div className="mb-4">
            <div className="mb-1.5 flex items-center justify-between text-caption font-semibold text-ink-muted">
              <span>Redemption amount</span>
              <span className="font-mono font-bold text-ink">{inr(amount)}</span>
            </div>
            <input
              type="range"
              min={50000}
              max={sliderMax}
              step={5000}
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
              aria-label="Redemption amount"
              className="
                w-full cursor-pointer appearance-none rounded-full bg-surface-3
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40
                [&::-webkit-slider-thumb]:h-[18px] [&::-webkit-slider-thumb]:w-[18px]
                [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2
                [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:bg-royal
                [&::-webkit-slider-thumb]:shadow-sm
                [&::-moz-range-thumb]:h-[18px] [&::-moz-range-thumb]:w-[18px]
                [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:rounded-full
                [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-white
                [&::-moz-range-thumb]:bg-royal
              "
              style={{ height: 6 }}
            />
            <div className="mt-1 flex justify-between font-mono text-[10px] text-ink-faint">
              <span>₹50,000</span>
              <span>{inr(sliderMax)}</span>
            </div>
          </div>

          {/* Holding period toggle (range 0–1 step 1) */}
          <div>
            <div className="mb-1.5 flex items-center justify-between text-caption font-semibold text-ink-muted">
              <span>Holding period</span>
              <span className="font-mono font-bold text-ink">{holdingLabel}</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={1}
              value={holding}
              onChange={(e) => setHolding(Number(e.target.value) as 0 | 1)}
              aria-label="Holding period: 0 for short-term, 1 for long-term"
              className="
                w-full cursor-pointer appearance-none rounded-full bg-surface-3
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40
                [&::-webkit-slider-thumb]:h-[18px] [&::-webkit-slider-thumb]:w-[18px]
                [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2
                [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:bg-royal
                [&::-webkit-slider-thumb]:shadow-sm
                [&::-moz-range-thumb]:h-[18px] [&::-moz-range-thumb]:w-[18px]
                [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:rounded-full
                [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-white
                [&::-moz-range-thumb]:bg-royal
              "
              style={{ height: 6 }}
            />
            <div className="mt-1 flex justify-between font-mono text-[10px] text-ink-faint">
              <span>&lt; 1 yr (STCG)</span>
              <span>&gt; 1 yr (LTCG)</span>
            </div>
          </div>
        </div>

        {/* RIGHT — live breakdown */}
        <div className="flex flex-col">
          <p className="mb-3 text-small font-bold text-ink">Tax breakdown</p>

          <div className="flex-1 divide-y divide-line rounded-xl border border-line">
            <TaxRow label="Redemption value"   value={inr(amount)}        />
            <TaxRow label="Invested (cost)"    value={inr(cost)}          />
            <TaxRow
              label="Capital gain"
              value={(gain >= 0 ? '+' : '') + inr(gain)}
              valueTone="emerald"
            />
            <TaxRow label={exemptLabel}        value={exemptDisplay}      />
            <TaxRow label="Exit load"          value="₹0"                 />
            <TaxRow label={taxLabel}           value={inr(tax)} bold />
          </div>

          {/* Net-in-hand highlight */}
          <div className="mt-3 flex items-center justify-between rounded-xl bg-emerald/[0.08] px-4 py-3.5">
            <span className="text-small font-semibold text-ink-secondary">
              Net in your hand
            </span>
            <span className="font-mono text-h3 font-extrabold text-emerald">
              {inr(net)}
            </span>
          </div>
        </div>
      </div>

      <WhatThisMeans>{TAX.meaning}</WhatThisMeans>
    </Panel>
  );
}

function TaxRow({
  label,
  value,
  bold = false,
  valueTone,
}: {
  label: string;
  value: string;
  bold?: boolean;
  valueTone?: 'emerald';
}) {
  return (
    <div className="flex items-center justify-between px-3.5 py-2.5">
      <span className={cn('text-caption text-ink-muted', bold && 'font-bold text-ink')}>
        {label}
      </span>
      <span
        className={cn(
          'font-mono text-caption font-semibold text-ink',
          bold && 'font-bold',
          valueTone === 'emerald' && 'text-emerald',
        )}
      >
        {value}
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// S18 — TRANSACTION HISTORY
// ─────────────────────────────────────────────────────────────────────────────

type TxnFilter = 'all' | 'sip' | 'lumpsum';

const FILTER_OPTIONS: { key: TxnFilter; label: string }[] = [
  { key: 'all',     label: 'All'      },
  { key: 'sip',     label: 'SIP'      },
  { key: 'lumpsum', label: 'Lumpsum'  },
];

const TXN_TYPE_LABEL: Record<string, string> = {
  purchase: 'Purchase',
  sip: 'SIP',
  redemption: 'Redemption',
  switch_in: 'Switch In',
  switch_out: 'Switch Out',
  dividend_payout: 'Div Payout',
  dividend_reinvest: 'Div Reinvest',
};
function txnTypeLabel(t: string): string {
  return TXN_TYPE_LABEL[t] ?? t;
}

const TXN_PAGE_SIZE = 10;

export function TransactionsSection({ portfolioId, isin }: { portfolioId: string; isin: string }) {
  const [filter, setFilter] = React.useState<TxnFilter>('all');
  const [visibleLimit, setVisibleLimit] = React.useState(TXN_PAGE_SIZE);
  const { data: envelope, isLoading, isError, refetch } = usePortfolioTransactions(portfolioId, {
    isin,
    limit: visibleLimit,
  });
  const status: DataStatus = !portfolioId
    ? 'empty'
    : isLoading
    ? 'loading'
    : isError
    ? 'error'
    : envelope?.status ?? 'empty';

  const payload = envelope?.data;
  const allRows = payload?.transactions ?? [];
  const rows: Transaction[] = filter === 'all'
    ? allRows
    : filter === 'sip'
    ? allRows.filter((t) => t.txn_type === 'sip')
    : allRows.filter((t) => t.txn_type !== 'sip');
  const total = payload?.total ?? 0;
  const remaining = Math.max(0, total - allRows.length);

  return (
    <DataState
      status={status}
      reason={envelope?.meta.reason ?? null}
      emptyCopy="Upload your CAS statement to see your transactions for this fund here."
      onRetry={() => refetch()}
      skeleton={
        <div className="flex flex-col gap-2">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full rounded-xl" />)}
        </div>
      }
    >
      {allRows.length === 0 ? (
        <Panel className="p-6 text-center">
          <p className="text-small font-medium text-ink">No transactions recorded for this fund yet.</p>
        </Panel>
      ) : (
        <Panel className="p-5 sm:p-6">
          {/* Filter chips */}
          <div className="mb-4 flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by transaction type">
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => setFilter(opt.key)}
                aria-pressed={filter === opt.key}
                className={cn(
                  'rounded-lg border px-3.5 py-1.5 font-mono text-caption font-semibold transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                  filter === opt.key
                    ? 'border-transparent bg-surface-3 text-ink shadow-sm'
                    : 'border-line bg-surface text-ink-muted hover:text-ink',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-small">
              <thead>
                <tr className="border-b border-line bg-surface-2">
                  {['Date', 'Type', 'Amount', 'NAV', 'Units'].map((h, i) => (
                    <th
                      key={h}
                      className={cn(
                        'px-3 py-2.5 font-mono text-[9.5px] font-bold uppercase tracking-[0.05em] text-ink-muted',
                        i >= 2 ? 'text-right' : 'text-left',
                      )}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((txn) => (
                  <tr key={txn.id} className="hover:bg-surface-2/60">
                    <td className="whitespace-nowrap px-3 py-3 font-mono text-caption text-ink-secondary">
                      {txn.txn_date}
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className={cn(
                          'inline-block rounded-md px-2 py-px font-mono text-[10px] font-bold',
                          txn.txn_type === 'sip'
                            ? 'bg-royal/10 text-royal'
                            : 'bg-cyan/10 text-cyan',
                        )}
                      >
                        {txnTypeLabel(txn.txn_type)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-caption font-semibold text-ink">
                      {inr(Math.abs(txn.amount))}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-caption text-ink-secondary">
                      {txn.nav_or_price != null ? `₹${txn.nav_or_price.toFixed(2)}` : '—'}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-caption text-ink-secondary">
                      {txn.units.toLocaleString('en-IN')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {remaining > 0 && (
            <button
              onClick={() => setVisibleLimit((n) => n + TXN_PAGE_SIZE)}
              className="
                mt-3 w-full rounded-xl border border-line bg-surface-2 py-2.5
                text-small font-semibold text-ink-muted
                hover:bg-surface-3 hover:text-ink
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40
                transition-colors
              "
            >
              View {Math.min(TXN_PAGE_SIZE, remaining)} more (of {total}) →
            </button>
          )}
        </Panel>
      )}
    </DataState>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// S19 — ALTERNATIVES
// ─────────────────────────────────────────────────────────────────────────────

/** Peer's return field, preferring 3Y and falling back to 1Y (both labeled so the
 * period shown is never ambiguous). null when neither is available yet. */
function peerReturn(peer: FundPeer): { label: string; v: string } {
  if (peer.return_3y_pct != null) return { label: '3Y ret', v: `${peer.return_3y_pct >= 0 ? '+' : ''}${peer.return_3y_pct.toFixed(1)}%` };
  if (peer.return_1y_pct != null) return { label: '1Y ret', v: `${peer.return_1y_pct >= 0 ? '+' : ''}${peer.return_1y_pct.toFixed(1)}%` };
  return { label: 'Return', v: '—' };
}
function peerRisk(peer: FundPeer): string {
  return peer.volatility_pct != null ? `${peer.volatility_pct.toFixed(1)}% swings` : '—';
}
function peerExpense(peer: FundPeer): string {
  return peer.expense_ratio_pct != null ? `${peer.expense_ratio_pct.toFixed(2)}%` : '—';
}
function peerName(peer: FundPeer): string {
  return peer.fund_name_short ?? peer.scheme_name;
}

export function AlternativesSection({ isin }: { isin: string }) {
  const { data: env, isLoading, isError, refetch } = useFundPeers(isin);
  const peers = env?.data?.peers ?? [];
  const status = isLoading ? 'loading' : isError ? 'error' : (peers.length ? 'present' : 'empty');
  // Alternatives = the 3 best-ranked peers (not just nearest-rank — §17 W1 decision #3).
  const alternatives = [...peers].sort((a, b) => a.category_rank - b.category_rank).slice(0, 3);

  return (
    <DataState
      status={status}
      emptyCopy="We don't have alternatives for this fund's category yet."
      onRetry={refetch}
      skeleton={<Skeleton className="h-40 w-full rounded-2xl" />}
    >
      <div className="grid gap-4 sm:grid-cols-1 md:grid-cols-3">
        {alternatives.map((alt) => {
          const ret = peerReturn(alt);
          return (
            <div
              key={alt.isin}
              className="
                flex flex-col rounded-2xl border border-line bg-surface p-4 shadow-sm
              "
            >
              {/* Tag pill — factual (category rank), never a subjective claim */}
              <span
                className={cn(
                  'mb-3 inline-block self-start rounded-lg border px-2.5 py-1',
                  'font-mono text-[9.5px] font-bold uppercase tracking-[0.05em]',
                  TAG_TINT.royal,
                )}
              >
                Category rank #{alt.category_rank}
              </span>

              {/* Fund identity */}
              <Link href={`/mf/fund/${alt.isin}`} className="mb-3 block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded">
                <div className="text-small font-bold leading-snug text-ink hover:underline">{peerName(alt)}</div>
                <div className="mt-0.5 text-caption text-ink-muted">
                  {alt.amc_name ?? 'Unknown AMC'} · {peerRisk(alt)}
                </div>
              </Link>

              {/* 3-up metric mini-grid */}
              <div className="mb-4 grid grid-cols-3 gap-2">
                {/* Assessment — COMPLIANCE: label + band via FundScoreCell, NO score number.
                    band is null — W1 doesn't serve a confidence band on peers yet. */}
                <MetricCell label="Assessment">
                  <FundScoreCell
                    label={(alt.verb_label ?? 'insufficient_data') as Label}
                    confidenceBand={null}
                    ringSize={28}
                    stacked
                    className="w-full"
                  />
                </MetricCell>
                <MetricCell label={ret.label}>
                  <span className="font-mono text-caption font-bold text-emerald">{ret.v}</span>
                </MetricCell>
                <MetricCell label="Expense">
                  <span className="font-mono text-caption font-bold text-ink">{peerExpense(alt)}</span>
                </MetricCell>
              </div>

              {/* Compare CTA — decorative, compare page is a later build */}
              <button
                className="
                  mt-auto w-full rounded-xl border border-line bg-surface-2 py-2
                  text-small font-semibold text-ink-muted
                  hover:bg-surface-3 hover:text-ink
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40
                  transition-colors
                "
              >
                ⇄ Compare with this fund
              </button>
            </div>
          );
        })}
      </div>
    </DataState>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// S20 — SIMILAR FUNDS (horizontal scroll carousel)
// ─────────────────────────────────────────────────────────────────────────────

export function SimilarSection({ isin }: { isin: string }) {
  const { data: env, isLoading, isError, refetch } = useFundPeers(isin);
  const peers = env?.data?.peers ?? [];
  const status = isLoading ? 'loading' : isError ? 'error' : (peers.length ? 'present' : 'empty');
  // Similar = the nearest-rank peers, in the order the backend already returns them.
  const similar = peers.slice(0, 5);

  return (
    <DataState
      status={status}
      emptyCopy="We don't have similar funds for this category yet."
      onRetry={refetch}
      skeleton={<Skeleton className="h-40 w-full rounded-2xl" />}
    >
      <div
        className="flex gap-3.5 overflow-x-auto pb-2 [scroll-snap-type:x_mandatory]"
        role="list"
        aria-label="Similar funds"
      >
        {similar.map((fund) => (
          <Link
            key={fund.isin}
            href={`/mf/fund/${fund.isin}`}
            role="listitem"
            className="
              flex w-[220px] flex-none scroll-snap-start flex-col
              rounded-2xl border border-line bg-surface p-4 shadow-sm
              [scroll-snap-align:start]
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40
            "
          >
            {/* Avatar + name */}
            <div className="mb-3 flex items-center gap-2.5">
              <FundAvatar name={peerName(fund)} />
              <div className="min-w-0">
                <div className="truncate text-caption font-bold leading-snug text-ink">
                  {peerName(fund)}
                </div>
                <div className="text-[10px] text-ink-muted">{fund.amc_name ?? 'Unknown AMC'}</div>
              </div>
            </div>

            {/* 3-up mini-grid: assessment / return / risk */}
            <div className="mb-4 grid grid-cols-3 gap-1.5">
              {/* Assessment — COMPLIANCE: label + band via FundScoreCell, NO score number.
                  band is null — W1 doesn't serve a confidence band on peers yet. */}
              <MetricCell label="Assessment">
                <FundScoreCell
                  label={(fund.verb_label ?? 'insufficient_data') as Label}
                  confidenceBand={null}
                  ringSize={28}
                  stacked
                  className="w-full"
                />
              </MetricCell>
              <MetricCell label={peerReturn(fund).label}>
                <span className="font-mono text-caption font-bold text-emerald">{peerReturn(fund).v}</span>
              </MetricCell>
              <MetricCell label="Risk">
                <span className="font-mono text-[10px] font-semibold text-ink-secondary">
                  {peerRisk(fund)}
                </span>
              </MetricCell>
            </div>

            <span
              className="
                mt-auto block w-full rounded-xl border border-line bg-surface-2 py-2
                text-center text-caption font-semibold text-ink-muted
              "
            >
              Quick compare
            </span>
          </Link>
        ))}
      </div>
    </DataState>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// S21 — FAQ (accordion)
// ─────────────────────────────────────────────────────────────────────────────

export function FaqSection({ navLatest }: { navLatest?: number | null }) {
  // Seed open-state from FAQ[i].open
  const [openIndex, setOpenIndex] = React.useState<number | null>(
    () => FAQ.findIndex((f) => f.open === true),
  );

  const toggle = (i: number) =>
    setOpenIndex((prev) => (prev === i ? null : i));

  // W0 — interpolate the real NAV into the one FAQ answer that quotes it (§17);
  // every other answer stays the static educational preview copy.
  const navStr = navLatest != null ? `₹${navLatest.toFixed(2)}` : null;

  return (
    <Panel className="p-5 sm:p-6">
      <div className="divide-y divide-line">
        {FAQ.map((item, i) => {
          const isOpen = openIndex === i;
          const answer = navStr ? item.a.replaceAll('₹18.42', navStr) : item.a;
          return (
            <div key={item.q}>
              <button
                onClick={() => toggle(i)}
                aria-expanded={isOpen}
                className="
                  flex w-full items-center justify-between gap-4
                  py-4 text-left text-small font-semibold text-ink
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40
                "
              >
                <span>{item.q}</span>
                <span
                  aria-hidden="true"
                  className={cn(
                    'shrink-0 text-ink-muted transition-transform duration-200',
                    isOpen && 'rotate-180',
                  )}
                >
                  ▾
                </span>
              </button>

              {isOpen && (
                <p className="pb-4 text-small leading-relaxed text-ink-muted">
                  {answer}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared sub-component: centred metric cell used in alt/similar grids
// ─────────────────────────────────────────────────────────────────────────────

function MetricCell({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-between gap-1.5 rounded-xl bg-surface-2 p-2 text-center">
      {children}
      <span className="mt-auto font-mono text-[9px] font-semibold uppercase tracking-[0.04em] text-ink-muted">
        {label}
      </span>
    </div>
  );
}

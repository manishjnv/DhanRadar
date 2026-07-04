/**
 * Fund Detail V3 — sections D: Tax / Transactions / Alternatives / Similar / FAQ
 *
 * COMPLIANCE (non-negotiable #1, #2):
 *   - Alternatives and Similar render educational LABEL + confidence BAND via
 *     <FundScoreCell> — NEVER a 0–100 score number.
 *   - Returns %, expense %, ₹ tax amounts are factual → DOM-allowed.
 *   - No advisory verbs (buy/sell/hold/avoid/caution/switch) anywhere.
 *   - "kind: 'sip' | 'lumpsum'" keys in TXNS are fine (not advisory verbs).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { FundAvatar } from '@/components/mf/explore/FundAvatar';
import { FundScoreCell } from '@/components/mf/explore/FundScoreCell';
import { Panel, WhatThisMeans } from './parts';
import { TAX, TXNS, TXN_TOTAL, ALTERNATIVES, SIMILAR, FAQ } from './sampleData';

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

export function TaxSection() {
  const [amount, setAmount] = React.useState(TAX.defaultAmount);
  // 1 = LTCG (> 1 year), 0 = STCG (< 1 year)
  const [holding, setHolding] = React.useState<0 | 1>(1);

  // Live computation — mirrors HTML JS lines 1131-1145
  const cost    = TAX.costBasis;
  const gain    = Math.max(0, amount - cost);
  const isLT    = holding === 1;
  const exempt  = isLT ? Math.min(gain, TAX.ltcgExempt) : 0;
  const tax     = isLT
    ? Math.max(0, (gain - exempt) * TAX.ltcgRate)
    : gain * TAX.stcgRate;
  const net     = amount - tax;

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
              max={500000}
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
              <span>₹5,00,000</span>
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

export function TransactionsSection() {
  const [filter, setFilter] = React.useState<TxnFilter>('all');

  const rows = filter === 'all'
    ? TXNS
    : TXNS.filter((t) => t.kind === filter);

  return (
    <Panel className="p-5 sm:p-6">
      {/* Tools row */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {/* Search (decorative) */}
        <div className="relative min-w-[160px] flex-1">
          <svg
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted"
            width={14} height={14} viewBox="0 0 24 24"
            fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="M16 16 L21 21" />
          </svg>
          <input
            type="search"
            placeholder="Search transactions…"
            aria-label="Search transactions"
            className="
              h-9 w-full rounded-xl border border-line bg-surface-2
              pl-8 pr-3 text-small text-ink placeholder:text-ink-faint
              focus:outline-none focus:ring-2 focus:ring-royal/40
            "
          />
        </div>

        {/* Filter chips */}
        <div className="flex gap-1.5" role="group" aria-label="Filter by transaction type">
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
              <tr key={`${txn.date}-${txn.kind}-${txn.units}`} className="hover:bg-surface-2/60">
                <td className="whitespace-nowrap px-3 py-3 font-mono text-caption text-ink-secondary">
                  {txn.date}
                </td>
                <td className="px-3 py-3">
                  <span
                    className={cn(
                      'inline-block rounded-md px-2 py-px font-mono text-[10px] font-bold',
                      txn.kind === 'sip'
                        ? 'bg-royal/10 text-royal'
                        : 'bg-cyan/10 text-cyan',
                    )}
                  >
                    {txn.kind === 'sip' ? 'SIP' : 'Lumpsum'}
                  </span>
                </td>
                <td className="px-3 py-3 text-right font-mono text-caption font-semibold text-ink">
                  {txn.amount}
                </td>
                <td className="px-3 py-3 text-right font-mono text-caption text-ink-secondary">
                  ₹{txn.nav}
                </td>
                <td className="px-3 py-3 text-right font-mono text-caption text-ink-secondary">
                  {txn.units}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button
        className="
          mt-3 w-full rounded-xl border border-line bg-surface-2 py-2.5
          text-small font-semibold text-ink-muted
          hover:bg-surface-3 hover:text-ink
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40
          transition-colors
        "
      >
        View all {TXN_TOTAL} transactions →
      </button>
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// S19 — ALTERNATIVES
// ─────────────────────────────────────────────────────────────────────────────

export function AlternativesSection() {
  return (
    <div className="grid gap-4 sm:grid-cols-1 md:grid-cols-3">
      {ALTERNATIVES.map((alt) => (
        <div
          key={alt.name}
          className="
            flex flex-col rounded-2xl border border-line bg-surface p-4 shadow-sm
          "
        >
          {/* Tag pill */}
          <span
            className={cn(
              'mb-3 inline-block self-start rounded-lg border px-2.5 py-1',
              'font-mono text-[9.5px] font-bold uppercase tracking-[0.05em]',
              TAG_TINT[alt.tagTone] ?? 'bg-surface-2 text-ink-muted border-line',
            )}
          >
            {alt.tag}
          </span>

          {/* Fund identity */}
          <div className="mb-3">
            <div className="text-small font-bold leading-snug text-ink">{alt.name}</div>
            <div className="mt-0.5 text-caption text-ink-muted">
              {alt.amc} · {alt.risk} risk
            </div>
          </div>

          {/* 3-up metric mini-grid */}
          <div className="mb-4 grid grid-cols-3 gap-2">
            {/* Assessment — COMPLIANCE: label + band via FundScoreCell, NO score number */}
            <MetricCell label="Assessment">
              <FundScoreCell
                label={alt.label}
                confidenceBand={alt.band}
                ringSize={28}
                stacked
                className="w-full"
              />
            </MetricCell>
            <MetricCell label="3Y ret">
              <span className="font-mono text-caption font-bold text-emerald">{alt.ret}</span>
            </MetricCell>
            <MetricCell label="Expense">
              <span className="font-mono text-caption font-bold text-ink">{alt.expense}</span>
            </MetricCell>
          </div>

          {/* Compare CTA */}
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
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// S20 — SIMILAR FUNDS (horizontal scroll carousel)
// ─────────────────────────────────────────────────────────────────────────────

export function SimilarSection() {
  return (
    <div
      className="flex gap-3.5 overflow-x-auto pb-2 [scroll-snap-type:x_mandatory]"
      role="list"
      aria-label="Similar funds"
    >
      {SIMILAR.map((fund) => (
        <div
          key={fund.name}
          role="listitem"
          className="
            flex w-[220px] flex-none scroll-snap-start flex-col
            rounded-2xl border border-line bg-surface p-4 shadow-sm
            [scroll-snap-align:start]
          "
        >
          {/* Avatar + name */}
          <div className="mb-3 flex items-center gap-2.5">
            <FundAvatar name={fund.name} />
            <div className="min-w-0">
              <div className="truncate text-caption font-bold leading-snug text-ink">
                {fund.name}
              </div>
              <div className="text-[10px] text-ink-muted">{fund.amc}</div>
            </div>
          </div>

          {/* 3-up mini-grid: assessment / 3Y / risk */}
          <div className="mb-4 grid grid-cols-3 gap-1.5">
            {/* Assessment — COMPLIANCE: label + band via FundScoreCell, NO score number */}
            <MetricCell label="Assessment">
              <FundScoreCell
                label={fund.label}
                confidenceBand={fund.band}
                ringSize={28}
                stacked
                className="w-full"
              />
            </MetricCell>
            <MetricCell label="3Y">
              <span className="font-mono text-caption font-bold text-emerald">{fund.ret}</span>
            </MetricCell>
            <MetricCell label="Risk">
              <span className="font-mono text-[10px] font-semibold text-ink-secondary">
                {fund.risk}
              </span>
            </MetricCell>
          </div>

          <button
            className="
              mt-auto w-full rounded-xl border border-line bg-surface-2 py-2
              text-caption font-semibold text-ink-muted
              hover:bg-surface-3 hover:text-ink
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40
              transition-colors
            "
          >
            Quick compare
          </button>
        </div>
      ))}
    </div>
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

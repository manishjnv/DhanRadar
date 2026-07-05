/**
 * Fund Detail V3 — Section group A (S4, S5, S7, S8).
 *
 * COMPLIANCE: no 0–100 numeric score/grade/percentile/weight rendered.
 * No advisory verbs (buy/sell/hold/avoid/caution/switch) as visible text,
 * string literals, or object keys. Factual values (%, ₹, NAV) are allowed.
 * S4 (Portfolio Fit, 2026-07-06 P2) renders the real `fund.fit` envelope
 * (extends the ALREADY-SHIPPED GET /portfolio/{id}/fit — see insights/service.py)
 * — factual category/overlap facts only, never a verdict or recommended band.
 * S5 (My Investment, P1) renders the owner's OWN real numbers from the existing
 * `GET /portfolio/{id}/holdings` endpoint — DOM-allowed user facts (§13), never a
 * DhanRadar score. Its ELSS lock-in strip (P2) reads `holding.lockin`, present
 * only for ELSS/tax-saver holdings.
 *
 * S7 Fund Health (§10.7, W2) is wired to the real `fund.health` envelope
 * (served alongside `fund.analytics` on GET /mf/fund/{isin}/analytics).
 * S8 What Changed (§10.6, W2) is wired to the real `fund.changes` envelope
 * (GET /mf/fund/{isin}/events). No section in this file uses sampleData anymore.
 */
'use client';

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { useFundAnalytics, useFundEvents, useFundPortfolioFit } from '@/features/mf/api';
import { usePortfolioHoldings } from '@/features/portfolio/api';
import { useMe } from '@/features/auth/api';
import { DataState, type DataStatus } from '@/components/ui/DataState';
import { Skeleton } from '@/components/ui/Skeleton';
import { Panel, WhatThisMeans, TONE_TEXT } from './parts';
import { relativeTime } from '@/features/mood/relative-time';
import type { FundEvent } from '@/features/mf/types';

// ═══════════════════════════════════════════════════════════════════════════
// S4 — PORTFOLIO FIT (rewired to real data, 2026-07-06 P2 — no more sampleData)
//
// COMPLIANCE (§14.3 reframe): factual observation only — "how this fund sits
// next to YOUR portfolio", never a verdict ("Strong Fit") or a recommended
// allocation band. No advisory verbs (fit/suit/should/ideal/recommended).
// ═══════════════════════════════════════════════════════════════════════════
export function PortfolioFitSection({ portfolioId, isin }: { portfolioId: string; isin: string }) {
  // useMe() distinguishes "anonymous" (401, real empty state) from "signed-in, no
  // CAS yet" (portfolioId '' but a real session) — portfolioId alone can't tell
  // the two apart (both leave it '' upstream in FundDetailClientView).
  const { data: me, isLoading: meLoading, isError: meIsError } = useMe();
  const isAnonymous = !meLoading && (meIsError || !me);

  const { data: envelope, isLoading, isError, refetch } = useFundPortfolioFit(portfolioId, isin);

  if (meLoading) {
    return (
      <Panel className="p-5 sm:p-6">
        <Skeleton className="h-40 w-full rounded-2xl" />
      </Panel>
    );
  }

  if (isAnonymous) {
    return (
      <Panel className="p-5 sm:p-6">
        <DataState
          status="empty"
          emptyCopy="Sign in to compare this fund with your own portfolio."
        >
          <></>
        </DataState>
      </Panel>
    );
  }

  const status: DataStatus = !portfolioId
    ? 'empty'
    : isLoading
    ? 'loading'
    : isError
    ? 'error'
    : envelope?.status ?? 'empty';
  const fit = envelope?.data ?? null;
  const hasCategoryFact = fit?.category_allocation_pct != null;
  const hasOverlapList = !!fit && fit.overlap.length > 0;

  return (
    <Panel className="p-5 sm:p-6">
      <DataState
        status={status}
        reason={envelope?.meta.reason ?? null}
        emptyCopy="Upload your CAS statement to compare this fund with your own portfolio."
        onRetry={() => refetch()}
        skeleton={<Skeleton className="h-40 w-full rounded-2xl" />}
      >
        {fit && (
          <div className="space-y-4">
            {hasCategoryFact && (
              <p className="text-small leading-relaxed text-ink-secondary">
                You already hold{' '}
                <span className="font-mono font-semibold text-ink">
                  {fit.category_allocation_pct!.toFixed(1)}%
                </span>{' '}
                of your portfolio&apos;s value in this fund&apos;s category
                {fit.fund_count_in_category != null && (
                  <>
                    {' '}
                    across {fit.fund_count_in_category}{' '}
                    fund{fit.fund_count_in_category === 1 ? '' : 's'}
                  </>
                )}
                .
              </p>
            )}

            {hasOverlapList ? (
              <div>
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-ink-muted">
                  Disclosed-holdings overlap with funds you hold
                </div>
                <ul className="space-y-2">
                  {fit.overlap.map((entry) => (
                    <li
                      key={entry.holding_name}
                      className="rounded-[11px] bg-surface-2 px-3 py-2 text-small text-ink-secondary"
                    >
                      <span className="font-medium text-ink">{entry.holding_name}</span> shares{' '}
                      <span className="font-mono font-semibold text-ink">
                        {entry.overlap_pct.toFixed(1)}%
                      </span>{' '}
                      of disclosed holdings with this fund.
                    </li>
                  ))}
                </ul>
              </div>
            ) : fit.overlap_coverage ? (
              <p className="text-caption text-ink-muted">
                No shared disclosed holdings were found between the funds you hold and this fund.
              </p>
            ) : (
              <p className="text-caption text-ink-muted">
                Disclosed-holdings data isn&apos;t available yet for the funds you hold, so an
                overlap comparison isn&apos;t possible right now.
              </p>
            )}

            {!hasCategoryFact && !hasOverlapList && (
              <p className="text-caption text-ink-muted">{fit.observation}</p>
            )}
          </div>
        )}
      </DataState>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S5 — MY INVESTMENT (P1 — real data, filtered to this fund's ISIN)
// ═══════════════════════════════════════════════════════════════════════════

function inr(n: number): string {
  const sign = n < 0 ? '-' : '';
  return sign + '₹' + Math.abs(Math.round(n)).toLocaleString('en-IN');
}

/** ADR-0039 data-state tag — only shown for the non-default states (the normal
 * 'ledger_backed' case renders no tag, matching the rest of the app's convention
 * of only surfacing an integrity caveat when there IS one). */
const DATA_STATE_TAG: Partial<Record<string, string>> = {
  stated_only: 'From your statement — no transaction history yet',
  unpriced: 'Price pending — showing your cost value',
  placeholder: 'Fund match pending',
};

function NoHoldingCard() {
  return (
    <Panel className="p-6 text-center">
      <p className="text-small font-medium text-ink">You don&apos;t currently hold this fund.</p>
      <p className="mt-1 text-caption text-ink-muted">
        This section shows your own numbers once you hold this fund in your uploaded portfolio.
      </p>
      <Link
        href="/mf/portfolio"
        className="mt-3 inline-block rounded text-small font-medium text-royal underline underline-offset-2 hover:text-royal/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        View your portfolio →
      </Link>
    </Panel>
  );
}

/** ELSS per-installment lock-in strip (P2, net new) — one row per surviving BUY-type lot +
 * the totals line. Factual register only ("lock ends <date>" / "lock over") — never a nudge
 * like "free to sell now". Absent entirely for a non-ELSS holding (`holding.lockin` is null),
 * not rendered as an empty state — it simply doesn't apply. */
function ElssLockinStrip({ lockin }: { lockin: NonNullable<import('@/features/portfolio/api').Holding['lockin']> }) {
  return (
    <div className="mt-4 border-t border-white/[0.14] pt-4">
      <div className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-white/50">
        ELSS lock-in (3 years per instalment)
      </div>
      <ul className="mt-2 space-y-1.5">
        {lockin.lots.map((lot, i) => (
          <li key={i} className="flex items-center justify-between font-mono text-[12.5px] text-white/85">
            <span>{lot.txn_date} · {lot.units.toLocaleString('en-IN')} units</span>
            <span className={lot.locked ? 'text-white/70' : 'text-emerald'}>
              {lot.locked ? `lock ends ${lot.lock_until}` : 'lock over'}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-2 text-[11px] text-white/60">
        {lockin.locked_units.toLocaleString('en-IN')} units locked
        {lockin.free_units > 0 && <>, {lockin.free_units.toLocaleString('en-IN')} units lock over</>}
        {lockin.next_unlock_date && <> · next unlock {lockin.next_unlock_date}</>}
        {lockin.approximate && ' · approximate — some lots could not be matched exactly from your ledger'}
      </div>
    </div>
  );
}

export function MyInvestmentSection({ portfolioId, isin }: { portfolioId: string; isin: string }) {
  const { data: envelope, isLoading, isError, refetch } = usePortfolioHoldings(portfolioId);
  const status: DataStatus = !portfolioId
    ? 'empty'
    : isLoading
    ? 'loading'
    : isError
    ? 'error'
    : envelope?.status ?? 'empty';
  const holdings = envelope?.data?.holdings ?? [];
  const holding = holdings.find((h) => h.isin === isin) ?? null;

  const totalValue = holdings.reduce((sum, h) => sum + h.current_value, 0);
  const weightPct = holding && totalValue > 0 ? (holding.current_value / totalValue) * 100 : null;
  const avgCostPerUnit =
    holding && holding.units > 0 && holding.invested_amount != null
      ? holding.invested_amount / holding.units
      : null;
  const gain = holding && holding.invested_amount != null ? holding.current_value - holding.invested_amount : null;
  const gainPct = holding && gain != null && holding.invested_amount ? (gain / holding.invested_amount) * 100 : null;
  const tag = holding ? DATA_STATE_TAG[holding.data_state ?? ''] : undefined;

  return (
    <DataState
      status={status}
      reason={envelope?.meta.reason ?? null}
      emptyCopy="Upload your CAS statement to see your investment in this fund here."
      onRetry={() => refetch()}
      skeleton={<Skeleton className="h-56 w-full rounded-2xl" />}
    >
      {!holding ? (
        <NoHoldingCard />
      ) : (
        <div
          className="relative overflow-hidden rounded-2xl p-6 text-white shadow-lg"
          style={{
            background: 'linear-gradient(135deg,var(--dr-navy,#0B1F3A),#1E3A6E)',
          }}
        >
          {/* decorative radial glow */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-8 -top-12 h-48 w-48 rounded-full"
            style={{
              background: 'radial-gradient(circle, rgba(16,185,129,.22), transparent 70%)',
            }}
          />

          {/* top row: current value left, XIRR right */}
          <div className="relative flex flex-wrap items-start justify-between gap-3.5">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-white/60">
                Current Value
              </div>
              <div className="mt-1.5 font-mono text-[32px] font-extrabold leading-none tracking-[-0.025em] text-white">
                {inr(holding.current_value)}
              </div>
              {gain != null && (
                <div className="mt-2 font-mono text-small font-bold text-emerald">
                  {gain >= 0 ? '+' : ''}{inr(gain)}{gainPct != null ? ` (${gainPct >= 0 ? '+' : ''}${gainPct.toFixed(1)}%)` : ''} overall
                  {holding.day_change != null && (
                    <span className="ml-1.5" style={{ color: '#6EE7B7' }}>
                      {holding.day_change >= 0 ? '▲' : '▼'} {inr(Math.abs(holding.day_change))} today
                    </span>
                  )}
                </div>
              )}
            </div>
            <div className="text-right">
              <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-white/60">
                XIRR
              </div>
              <div
                className="mt-1.5 font-mono text-[26px] font-extrabold leading-none tracking-[-0.02em]"
                style={{ color: '#6EE7B7' }}
              >
                {holding.xirr_pct != null ? `${holding.xirr_pct >= 0 ? '+' : ''}${holding.xirr_pct.toFixed(1)}%` : '—'}
              </div>
            </div>
          </div>

          {tag && (
            <div className="relative mt-3">
              <span className="inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/10 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-white/70">
                {tag}
              </span>
            </div>
          )}

          {/* data grid — the user's own numbers only */}
          <div className="relative mt-5 grid grid-cols-2 gap-x-5 gap-y-4 border-t border-white/[0.14] pt-5 sm:grid-cols-4">
            <div>
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-white/50">Invested</div>
              <div className="mt-1.5 font-mono text-[15px] font-bold text-white">
                {holding.invested_amount != null ? inr(holding.invested_amount) : '—'}
              </div>
            </div>
            <div>
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-white/50">Units held</div>
              <div className="mt-1.5 font-mono text-[15px] font-bold text-white">{holding.units.toLocaleString('en-IN')}</div>
            </div>
            <div>
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-white/50">Avg cost / unit</div>
              <div className="mt-1.5 font-mono text-[15px] font-bold text-white">
                {avgCostPerUnit != null ? `₹${avgCostPerUnit.toFixed(2)}` : '—'}
              </div>
            </div>
            <div>
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-white/50">Current NAV</div>
              <div className="mt-1.5 font-mono text-[15px] font-bold text-white">
                {holding.current_nav != null ? `₹${holding.current_nav.toFixed(2)}` : '—'}
              </div>
            </div>
            <div>
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-white/50">Portfolio weight</div>
              <div className="mt-1.5 font-mono text-[15px] font-bold text-white">
                {weightPct != null ? `${weightPct.toFixed(1)}%` : '—'}
              </div>
            </div>
            <div>
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-white/50">As of</div>
              <div className="mt-1.5 font-mono text-[15px] font-bold text-white">{holding.as_of ?? '—'}</div>
            </div>
          </div>

          {/* no-suppress-ok: lockin is null for every non-ELSS holding by design (P2) — doesn't apply, not hidden data */}
          {holding.lockin && <ElssLockinStrip lockin={holding.lockin} />}
        </div>
      )}
    </DataState>
  );
}


// ═══════════════════════════════════════════════════════════════════════════
// S7 — FUND HEALTH DASHBOARD (traffic-light grid) — real, W2 §10.7
// ═══════════════════════════════════════════════════════════════════════════
const LIGHT_DOT: Record<'g' | 'y' | 'r' | 'grey', string> = {
  g: 'bg-emerald',
  y: 'bg-amber',
  r: 'bg-red',
  grey: 'bg-ink-faint',
};
const LIGHT_RING: Record<'g' | 'y' | 'r' | 'grey', string> = {
  g: 'shadow-[0_0_0_4px_rgba(0,179,134,0.15)]',
  y: 'shadow-[0_0_0_4px_rgba(245,166,35,0.15)]',
  r: 'shadow-[0_0_0_4px_rgba(229,72,77,0.15)]',
  grey: 'shadow-[0_0_0_4px_rgba(148,163,184,0.15)]',
};

export function FundHealthSection({ isin }: { isin: string }) {
  const { data, isLoading, isError, refetch } = useFundAnalytics(isin);
  const health = data?.health.data ?? null;
  const lights = health?.lights ?? [];
  const envStatus = data?.health.status ?? 'empty';
  const status = isLoading ? 'loading' : isError ? 'error' : (envStatus === 'present' && lights.length === 0 ? 'empty' : envStatus);

  return (
    <Panel className="p-5 sm:p-6">
      <DataState
        status={status}
        emptyCopy="We don't have a health read for this fund yet."
        onRetry={refetch}
        skeleton={<Skeleton className="h-40 w-full rounded-2xl" />}
      >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {lights.map((item) => (
          <div
            key={item.name}
            className="flex items-start gap-3 rounded-[13px] border border-line p-3.5"
          >
            {/* traffic-light dot with soft ring — grey = source not available yet */}
            <span
              aria-hidden="true"
              className={cn(
                'mt-[3px] h-3 w-3 shrink-0 rounded-full',
                LIGHT_DOT[item.light],
                LIGHT_RING[item.light],
              )}
            />
            <div className="min-w-0">
              <div className="text-small font-bold text-ink">{item.name}</div>
              <div className="mt-[3px] text-caption leading-snug text-ink-muted">
                {item.note}
              </div>
            </div>
          </div>
        ))}
      </div>
      </DataState>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S8 — WHAT CHANGED THIS MONTH (vertical timeline)
// ═══════════════════════════════════════════════════════════════════════════
const CHANGE_DOT: Record<'up' | 'down' | 'info', string> = {
  up:   'bg-emerald',
  down: 'bg-red',
  info: 'bg-royal',
};

/** Tone (up/down/info) from an event's own payload — no separate score, just the
 * facts it already carries (§17 W2: rank up/down from direction; TER down = positive;
 * everything else, including holding_change, is neutral). */
function eventTone(ev: FundEvent): 'up' | 'down' | 'info' {
  if (ev.event_type === 'rank_change') {
    const direction = ev.payload.direction;
    return direction === 'up' ? 'up' : direction === 'down' ? 'down' : 'info';
  }
  if (ev.event_type === 'ter_change') {
    const oldTer = Number(ev.payload.old_ter);
    const newTer = Number(ev.payload.new_ter);
    return Number.isFinite(oldTer) && Number.isFinite(newTer) && newTer < oldTer ? 'up' : 'info';
  }
  return 'info'; // holding_change — a fact, not a positive/negative signal
}

export function WhatChangedSection({ isin }: { isin: string }) {
  const { data: env, isLoading, isError, refetch } = useFundEvents(isin);
  const events = env?.data?.events ?? [];
  const status = isLoading ? 'loading' : isError ? 'error' : (events.length ? 'present' : 'empty');

  return (
    <Panel className="p-5 sm:p-6">
      <DataState
        status={status}
        emptyCopy="No notable changes tracked yet."
        onRetry={refetch}
        skeleton={<Skeleton className="h-40 w-full rounded-2xl" />}
      >
        {/* timeline rail: relative container with left border as the line */}
        <div className="relative pl-[22px]">
          {/* vertical rail line */}
          <div
            aria-hidden="true"
            className="absolute bottom-[6px] left-[5px] top-[6px] w-[2px] bg-line"
          />

          {events.map((ev, i) => (
            <div
              key={i}
              className={cn('relative pb-4 last:pb-0')}
            >
              {/* colored dot */}
              <span
                aria-hidden="true"
                className={cn(
                  'absolute -left-[22px] top-[3px] h-3 w-3 shrink-0 rounded-full border-2 border-surface',
                  CHANGE_DOT[eventTone(ev)],
                )}
              />

              {/* plain text — server-templated summary, no HTML injection needed */}
              <div className="text-small leading-relaxed text-ink-secondary">
                {ev.summary}
              </div>
              <div className="mt-0.5 font-mono text-[11px] text-ink-faint">
                {relativeTime(ev.as_of)}
              </div>
            </div>
          ))}
        </div>
      </DataState>
    </Panel>
  );
}

/**
 * Invest wizard — shared primitives (chips, fund strip, stepper, footer,
 * order-summary panel, static reference/preview cards, projection math).
 *
 * Split out of InvestWizard.tsx purely to keep that file under control —
 * everything here is presentational or a pure function, no BSE call sites.
 *
 * COMPLIANCE (non-neg #1/#2): no advisory verbs, no numeric DhanRadar score.
 * The riskometer badge renders `risk_o_meter` TEXT only (e.g. "Moderately
 * High") — never a number, never a score ring.
 */
'use client';

import * as React from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';
import type { FundHead } from '@/features/mf/types';

// ---------------------------------------------------------------------------
// Fund type extension (server-api.ts / features/mf/types.ts do not yet
// declare these five fields — extend locally, per task instructions, rather
// than edit those shared files).
// ---------------------------------------------------------------------------
export type FundHeadExt = FundHead & {
  min_lumpsum_amount: number | null;
  min_sip_amount: number | null;
  exit_load_pct: number | null;
  exit_load_days: number | null;
  risk_o_meter: string | null;
};

// ---------------------------------------------------------------------------
// Chip — LIVE / BSE UAT / PREVIEW status pills (founder requirement: every
// card gets one so it's obvious what's real vs. static design data).
// ---------------------------------------------------------------------------
export type ChipKind = 'live' | 'uat' | 'preview';

const CHIP_STYLE: Record<ChipKind, { label: string; cls: string }> = {
  live:    { label: 'LIVE',     cls: 'bg-emerald/10 text-emerald' },
  uat:     { label: 'BSE UAT',  cls: 'bg-royal/5 text-royal' },
  preview: { label: 'PREVIEW',  cls: 'bg-surface-2 text-ink-muted' },
};

export function Chip({ kind, className }: { kind: ChipKind; className?: string }) {
  const s = CHIP_STYLE[kind];
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-caption font-medium whitespace-nowrap',
        s.cls,
        className,
      )}
    >
      {s.label}
    </span>
  );
}

export function ChipRow({ kinds, className }: { kinds: ChipKind[]; className?: string }) {
  return (
    <div className={cn('flex flex-wrap items-center gap-1.5', className)}>
      {kinds.map((k) => (
        <Chip key={k} kind={k} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------
export function formatINR(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return '₹' + Math.round(n).toLocaleString('en-IN');
}

export function formatINRPrecise(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

// ---------------------------------------------------------------------------
// Projection math (client-side, illustrative only — non-neg: never a promise)
// ---------------------------------------------------------------------------

/** Lumpsum compound growth: FV = P × (1 + r)^years. */
export function computeLumpsumFuture(amount: number, years: number, annualRatePct: number): number {
  return amount * Math.pow(1 + annualRatePct / 100, years);
}

/** Flat monthly SIP future value (monthly compounding, ordinary annuity). */
export function computeSipFuture(monthly: number, years: number, annualRatePct: number): number {
  const r = annualRatePct / 100 / 12;
  const n = years * 12;
  if (r === 0) return monthly * n;
  return monthly * ((Math.pow(1 + r, n) - 1) / r) * (1 + r);
}

/** Step-up SIP: instalment rises stepUpPct at each 12-month anniversary.
 * Simple year-by-year loop — no closed form needed for a preview chart. */
export function computeStepUpSipFuture(
  monthly: number,
  years: number,
  annualRatePct: number,
  stepUpPct: number,
): { invested: number; corpus: number } {
  const r = annualRatePct / 100 / 12;
  let corpus = 0;
  let invested = 0;
  let instalment = monthly;
  for (let y = 0; y < years; y++) {
    for (let m = 0; m < 12; m++) {
      corpus = corpus * (1 + r) + instalment;
      invested += instalment;
    }
    instalment = instalment * (1 + stepUpPct / 100);
  }
  return { invested, corpus };
}

/** Year-by-year corpus values for the growth-bar preview (flat SIP or lumpsum). */
export function yearlyCorpusSeries(
  isLumpsum: boolean,
  amount: number,
  years: number,
  annualRatePct: number,
): number[] {
  const out: number[] = [];
  for (let y = 1; y <= years; y++) {
    out.push(isLumpsum ? computeLumpsumFuture(amount, y, annualRatePct) : computeSipFuture(amount, y, annualRatePct));
  }
  return out;
}

// ---------------------------------------------------------------------------
// Riskometer badge — TEXT only, no number, no score ring (non-neg #2).
// ---------------------------------------------------------------------------
export function RiskBadge({ risk }: { risk: string | null | undefined }) {
  return (
    <span className="inline-flex items-center rounded-md bg-amber/10 px-2.5 py-1 text-caption font-medium text-amber">
      {risk ? `${risk} risk` : 'Risk — —'}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Fund summary strip — shared across every step.
// ---------------------------------------------------------------------------
export function FundSummaryStrip({ fund }: { fund: FundHeadExt }) {
  const name = fund.fund_name_short || fund.scheme_name;
  const mark = (fund.amc_name || name || '??').slice(0, 2).toUpperCase();
  return (
    <Card>
      <div className="flex items-center gap-4 p-4 sm:p-5">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-royal text-body font-semibold text-white sm:h-14 sm:w-14">
          {mark}
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-h3 font-medium text-ink">{name}</h2>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {fund.amc_name && (
              <span className="rounded-md bg-surface-2 px-2 py-0.5 text-caption text-ink-secondary">{fund.amc_name}</span>
            )}
            {(fund.category || fund.sebi_category) && (
              <span className="rounded-md bg-royal/5 px-2 py-0.5 text-caption text-royal">
                {fund.category || fund.sebi_category}
              </span>
            )}
            <RiskBadge risk={fund.risk_o_meter} />
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 border-t border-line sm:grid-cols-3 lg:grid-cols-6">
        <QuickStat label="NAV" value={fund.nav_latest != null ? formatINRPrecise(fund.nav_latest) : '—'} />
        <QuickStat
          label="3Y return"
          value={fund.return_3y_pct != null ? `${fund.return_3y_pct.toFixed(1)}%` : '—'}
          tone={fund.return_3y_pct != null && fund.return_3y_pct >= 0 ? 'up' : undefined}
        />
        <QuickStat label="Annual cost" value={fund.expense_ratio_pct != null ? `${fund.expense_ratio_pct.toFixed(2)}%` : '—'} />
        <QuickStat label="Min. SIP" value={fund.min_sip_amount != null ? formatINR(fund.min_sip_amount) : '—'} />
        <QuickStat label="Min. lumpsum" value={fund.min_lumpsum_amount != null ? formatINR(fund.min_lumpsum_amount) : '—'} />
        <QuickStat
          label="Exit load"
          value={
            fund.exit_load_pct != null
              ? fund.exit_load_pct === 0
                ? 'Nil'
                : `${fund.exit_load_pct}% · ${fund.exit_load_days ?? '—'}d`
              : '—'
          }
        />
      </div>
    </Card>
  );
}

function QuickStat({ label, value, tone }: { label: string; value: string; tone?: 'up' }) {
  return (
    <div className="border-b border-r border-line p-3 last:border-r-0 sm:border-b-0">
      <div className="text-micro font-medium uppercase tracking-wide text-ink-faint">{label}</div>
      <div className={cn('mt-0.5 text-small font-medium', tone === 'up' ? 'text-emerald' : 'text-ink')}>{value}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stepper — 6 clickable steps, sticky under the header.
// ---------------------------------------------------------------------------
export const STEP_TITLES = [
  'Investment details',
  'Verification',
  'SIP setup',
  'Payment',
  'Review',
  'Done',
];

export function Stepper({
  current,
  skipStep3,
  onJump,
}: {
  current: number;
  skipStep3: boolean;
  onJump: (n: number) => void;
}) {
  return (
    // ponytail: header height isn't exposed as a CSS var (only dev-banner-h /
    // ticker-h are) — top-12 approximates SiteHeader's real height. Upgrade
    // if the header ever exports its own var.
    <nav
      aria-label="Transaction progress"
      className="sticky top-12 z-20 -mx-4 border-b border-line bg-surface sm:-mx-6"
    >
      <div className="flex gap-0 overflow-x-auto px-4 sm:px-6">
        {STEP_TITLES.map((title, i) => {
          const n = i + 1;
          const done = n < current;
          const on = n === current;
          const skipped = skipStep3 && n === 3;
          return (
            <button
              key={n}
              type="button"
              onClick={() => onJump(n)}
              className={cn(
                'flex min-w-[128px] flex-1 items-center gap-2 border-b-2 border-transparent px-2 py-3 text-left',
                on && 'border-royal',
              )}
            >
              <span
                className={cn(
                  'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-caption font-semibold',
                  done ? 'border-emerald/40 bg-emerald/10 text-emerald' : 'border-line bg-surface-2 text-ink-muted',
                  on && 'border-royal bg-royal text-white',
                )}
              >
                {done ? '✓' : n}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-caption font-medium uppercase tracking-wide text-ink-faint">
                  Step {n}{skipped ? ' · skipped' : ''}
                </span>
                <span className={cn('block truncate text-small font-medium', on ? 'text-ink' : 'text-ink-secondary')}>
                  {title}
                </span>
              </span>
            </button>
          );
        })}
      </div>
      <div className="h-0.5 bg-surface-2">
        <div className="h-full bg-royal transition-all" style={{ width: `${Math.round((current / 6) * 100)}%` }} />
      </div>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Sticky footer — Back / Continue.
// ---------------------------------------------------------------------------
export function StickyFooter({
  label,
  value,
  onBack,
  backHidden,
  onNext,
  nextLabel,
  nextDisabled,
  nextBusy,
  onOpenSheet,
}: {
  label: string;
  value: string;
  onBack: () => void;
  backHidden: boolean;
  onNext: () => void;
  nextLabel: string;
  nextDisabled?: boolean;
  nextBusy?: boolean;
  onOpenSheet?: () => void;
}) {
  return (
    <footer className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/97 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
        <div className="min-w-0 flex-1">
          <div className="truncate text-micro font-medium uppercase tracking-wide text-ink-faint">{label}</div>
          <div className="truncate text-small font-medium text-ink">{value}</div>
        </div>
        {onOpenSheet && (
          <Button variant="ghost" size="sm" className="min-[1100px]:hidden" onClick={onOpenSheet}>
            Summary
          </Button>
        )}
        {!backHidden && (
          <Button variant="ghost" size="sm" onClick={onBack}>
            ← Back
          </Button>
        )}
        <Button size="sm" onClick={onNext} disabled={nextDisabled || nextBusy}>
          {nextBusy ? 'Working…' : nextLabel}
        </Button>
      </div>
    </footer>
  );
}

// ---------------------------------------------------------------------------
// Order summary panel content — shared between the desktop rail and the
// mobile bottom sheet.
// ---------------------------------------------------------------------------
export function OrderSummaryPanel({
  fund,
  investType,
  amount,
  frequency,
  debitDate,
  orderId,
}: {
  fund: FundHeadExt;
  investType: 'sip' | 'lumpsum';
  amount: number;
  frequency: string;
  debitDate: number;
  orderId: string | null;
}) {
  const name = fund.fund_name_short || fund.scheme_name;
  return (
    <div>
      <div className="rounded-t-lg bg-navy p-4 text-white">
        <div className="text-micro font-medium uppercase tracking-wide text-white/60">Order summary</div>
        <div className="mt-1 text-h3 font-medium">{name}</div>
      </div>
      <Row k="Plan" v={`${fund.plan_type ?? '—'} · ${fund.option_type ?? '—'}`} />
      <Row k="Type" v={investType === 'sip' ? `${cap(frequency)} SIP` : 'One-time lumpsum'} />
      <Row k="Amount" v={investType === 'sip' ? `${formatINR(amount)} / ${frequency}` : formatINR(amount)} />
      {investType === 'sip' && <Row k="Debit date" v={`${debitDate}${ordinalSuffix(debitDate)} of month`} />}
      <Row k="Commission" v={<span className="text-emerald">₹0 · direct plan</span>} />
      <Row k="Transaction fee" v={<span className="text-emerald">₹0</span>} />
      <Row k="Annual fund cost" v={fund.expense_ratio_pct != null ? `${fund.expense_ratio_pct.toFixed(2)}% p.a.` : '—'} />
      <div className="flex items-center justify-between gap-3 bg-surface-2 px-4 py-3">
        <span className="text-small font-medium text-ink">Debited today</span>
        <span className="text-h3 font-medium text-ink">{formatINR(amount)}</span>
      </div>
      {orderId && (
        <div className="border-t border-line px-4 py-3">
          <div className="text-micro font-medium uppercase tracking-wide text-ink-faint">Order</div>
          <div className="text-small font-medium text-ink">{orderId}</div>
        </div>
      )}
      <div className="border-t border-line p-4">
        <div className="rounded-md border border-amber/30 bg-amber/10 p-3">
          <div className="text-caption font-semibold uppercase tracking-wide text-amber">
            Risk — {fund.risk_o_meter ?? '—'}
          </div>
          <p className="mt-1 text-caption text-ink-secondary">
            Value can fall as well as rise. This is educational information, not investment advice.
          </p>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {['🔒 256-bit TLS', '⚡ T+1 units', '↩ Free cancel anytime'].map((t) => (
            <span key={t} className="rounded-md bg-surface-2 px-2 py-1 text-caption font-medium text-ink-secondary">
              {t}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5 text-small">
      <span className="text-ink-muted">{k}</span>
      <span className="text-right font-medium text-ink">{v}</span>
    </div>
  );
}

function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function ordinalSuffix(n: number): string {
  if (n % 10 === 1 && n % 100 !== 11) return 'st';
  if (n % 10 === 2 && n % 100 !== 12) return 'nd';
  if (n % 10 === 3 && n % 100 !== 13) return 'rd';
  return 'th';
}

// ---------------------------------------------------------------------------
// "What this means for you" plain-English callout.
// ---------------------------------------------------------------------------
export function MeansForYouCallout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-4 flex gap-3 rounded-md border border-royal/20 bg-royal/5 p-3">
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-royal text-caption font-bold text-white">
        i
      </span>
      <div>
        <div className="text-caption font-semibold uppercase tracking-wide text-royal">What this means for you</div>
        <p className="mt-0.5 text-small leading-relaxed text-ink-secondary">{children}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Projection trio + growth bars (illustrative — non-neg: never a promise).
// ---------------------------------------------------------------------------
export function ProjectionTrio({
  conservative,
  expected,
  optimistic,
  investedLabel,
}: {
  conservative: number;
  expected: number;
  optimistic: number;
  investedLabel: (v: number) => string;
}) {
  const tiles = [
    { l: 'Conservative · 9%', v: conservative },
    { l: 'Expected · 13%', v: expected, hi: true },
    { l: 'Optimistic · 16%', v: optimistic },
  ];
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {tiles.map((t) => (
        <div
          key={t.l}
          className={cn('rounded-md border border-line p-3', t.hi && 'border-emerald/30 bg-emerald/10')}
        >
          <div className="text-caption font-medium text-ink-secondary">{t.l}</div>
          <div className="mt-1 text-h3 font-medium text-ink">{formatINRLakh(t.v)}</div>
          <div className="mt-0.5 text-caption text-ink-faint">{investedLabel(t.v)}</div>
        </div>
      ))}
    </div>
  );
}

export function formatINRLakh(v: number): string {
  if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`;
  if (v >= 100000) return `₹${(v / 100000).toFixed(2)} L`;
  return formatINR(v);
}

export function GrowthBars({ values }: { values: number[] }) {
  const max = Math.max(...values, 1);
  return (
    <div>
      <div className="mt-4 flex h-20 items-end gap-1.5" aria-hidden="true">
        {values.map((v, i) => (
          <div
            key={i}
            className={cn(
              'flex-1 rounded-t bg-royal/60',
              i === values.length - 1 && 'bg-emerald',
            )}
            style={{ height: `${Math.max(6, Math.round((v / max) * 100))}%` }}
          />
        ))}
      </div>
      <div className="mt-1.5 flex gap-1.5">
        {values.map((_, i) => (
          <span key={i} className="flex-1 text-center text-micro text-ink-faint">
            Yr{i + 1}
          </span>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Static PREVIEW cards — smart suggestions (step 1), disabled CTAs.
// ---------------------------------------------------------------------------
export function SmartSuggestionsGrid() {
  const cards = [
    { title: 'Smart SIP amount', badge: 'AI', heading: 'A different amount may fit your surplus', body: 'Based on your surplus and goal gap, an adjusted SIP amount could close your goal faster.', cta: 'Apply' },
    { title: 'Tax saving', badge: '₹46,800', heading: 'ELSS could reduce tax outgo', body: 'You may have 80C headroom left. Shifting part of this into ELSS is an option to consider.', cta: 'See ELSS funds' },
    { title: 'Portfolio balance', badge: 'Fit check', heading: 'This purchase shifts your category mix', body: 'This fund’s category may push one segment above your usual allocation. Something to be aware of.', cta: 'Split investment' },
  ];
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {cards.map((c) => (
        <div key={c.title} className="rounded-md border border-line bg-surface">
          <div className="flex items-center gap-2 border-b border-line bg-surface-2 px-3 py-2">
            <span className="text-caption font-medium text-ink-secondary">{c.title}</span>
            <span className="ml-auto rounded bg-royal/5 px-1.5 py-0.5 text-micro font-semibold text-royal">{c.badge}</span>
          </div>
          <div className="p-3">
            <h4 className="text-small font-semibold text-ink">{c.heading}</h4>
            <p className="mt-1 text-caption leading-relaxed text-ink-secondary">{c.body}</p>
            <Button variant="ghost" size="sm" className="mt-3" disabled>
              {c.cta}
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Verification row (step 2)
// ---------------------------------------------------------------------------
export type RowTone = 'ok' | 'warn' | 'bad' | 'unknown';

const TONE_DOT: Record<RowTone, string> = {
  ok: 'border-emerald/40 bg-emerald/10 text-emerald',
  warn: 'border-amber/40 bg-amber/10 text-amber',
  bad: 'border-red/40 bg-red/5 text-red',
  unknown: 'border-line bg-surface-2 text-ink-muted',
};
const TONE_SYMBOL: Record<RowTone, string> = { ok: '✓', warn: '!', bad: '✕', unknown: '—' };
const TONE_STAT: Record<RowTone, string> = {
  ok: 'bg-emerald/10 text-emerald',
  warn: 'bg-amber/10 text-amber',
  bad: 'bg-red/5 text-red',
  unknown: 'bg-surface-2 text-ink-muted',
};

export function VerificationRow({
  tone,
  name,
  description,
  statusLabel,
  note,
  preview,
}: {
  tone: RowTone;
  name: string;
  description: string;
  statusLabel: string;
  note?: string;
  preview?: boolean;
}) {
  return (
    <div className="flex items-start gap-3 border-b border-line px-4 py-3 last:border-b-0">
      <span className={cn('mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-caption font-bold', TONE_DOT[tone])}>
        {TONE_SYMBOL[tone]}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-small font-medium text-ink">
          {name}
          {preview && <Chip kind="preview" />}
        </div>
        <div className="text-caption text-ink-muted">{description}</div>
        {note && <div className="mt-1 text-caption text-amber">{note}</div>}
      </div>
      <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-caption font-semibold', TONE_STAT[tone])}>
        {statusLabel}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Payment method row (step 4)
// ---------------------------------------------------------------------------
export function PaymentMethodRow({
  icon,
  name,
  description,
  tag,
  chips,
  selected,
  disabled,
  onClick,
}: {
  icon: string;
  name: string;
  description: string;
  tag?: string;
  chips?: ChipKind[];
  selected: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'flex w-full items-center gap-3 rounded-md border p-3 text-left transition-colors',
        selected ? 'border-royal bg-royal/5' : 'border-line bg-surface',
        disabled && 'opacity-50',
      )}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-surface-2 text-body">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-1.5 text-small font-semibold text-ink">
          {name}
          {chips && <ChipRow kinds={chips} />}
        </span>
        <span className="block text-caption text-ink-muted">{description}</span>
      </span>
      {tag && <span className="shrink-0 rounded-md bg-surface-2 px-2 py-0.5 text-caption font-medium text-ink-secondary">{tag}</span>}
      <span className={cn('h-5 w-5 shrink-0 rounded-full border-2', selected ? 'border-royal' : 'border-line')}>
        {selected && <span className="m-auto mt-[3px] block h-2 w-2 rounded-full bg-royal" />}
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Timeline item (step 4 static "what happens after you pay" + step 6 tracking)
// ---------------------------------------------------------------------------
export function TimelineItem({
  state,
  name,
  description,
  time,
  last,
}: {
  state: 'done' | 'on' | 'pending';
  name: string;
  description: string;
  time?: string;
  last?: boolean;
}) {
  return (
    <div className="relative flex gap-3 pb-4 last:pb-0">
      {!last && <span className="absolute left-[11px] top-6 bottom-0 w-px bg-line" />}
      <span
        className={cn(
          'z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 bg-surface text-caption font-bold',
          state === 'done' && 'border-emerald bg-emerald text-white',
          state === 'on' && 'border-royal text-royal',
          state === 'pending' && 'border-line text-ink-faint',
        )}
      >
        {state === 'done' ? '✓' : state === 'on' ? '◉' : '○'}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="text-small font-semibold text-ink">{name}</span>
          {time && <span className="font-mono text-caption text-ink-faint">{time}</span>}
        </div>
        <div className="text-caption text-ink-muted">{description}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reference-state cards — collapsed <details>, PREVIEW only.
// ---------------------------------------------------------------------------
export interface MockState {
  title: string;
  badge: string;
  badgeTone: 'err' | 'emp' | 'load';
  icon: string;
  heading: string;
  body: string;
}

const BADGE_TONE_CLS: Record<MockState['badgeTone'], string> = {
  err: 'bg-red/5 text-red',
  emp: 'bg-surface-2 text-ink-muted',
  load: 'bg-royal/5 text-royal',
};

function MockStateCard({ m }: { m: MockState }) {
  return (
    <div className="rounded-md border border-line bg-surface">
      <div className="flex items-center gap-2 border-b border-line bg-surface-2 px-3 py-2">
        <span className="text-caption font-medium text-ink-secondary">{m.title}</span>
        <span className={cn('ml-auto rounded px-1.5 py-0.5 text-micro font-semibold', BADGE_TONE_CLS[m.badgeTone])}>{m.badge}</span>
      </div>
      <div className="p-3">
        <div className="text-h3 leading-none">{m.icon}</div>
        <h4 className="mt-2 text-small font-semibold text-ink">{m.heading}</h4>
        <p className="mt-1 text-caption leading-relaxed text-ink-secondary">{m.body}</p>
      </div>
    </div>
  );
}

export function ReferenceStatesDetails({ summary, states }: { summary: string; states: MockState[] }) {
  return (
    <details className="mt-4 rounded-md border border-line">
      <summary className="cursor-pointer select-none px-3 py-2 text-small font-medium text-ink-secondary">
        {summary} <Chip kind="preview" className="ml-1 align-middle" />
      </summary>
      <div className="grid grid-cols-1 gap-3 border-t border-line p-3 sm:grid-cols-3">
        {states.map((m) => (
          <MockStateCard key={m.title} m={m} />
        ))}
      </div>
    </details>
  );
}

export const STEP2_REFERENCE_STATES: MockState[] = [
  { title: 'New investor', badge: 'Empty', badgeTone: 'emp', icon: '👋', heading: 'First investment?', body: 'We verify you once. Every future investment then takes three taps.' },
  { title: 'Missing KYC', badge: 'Empty', badgeTone: 'emp', icon: '🪪', heading: 'KYC not found', body: 'Complete a video KYC with PAN and Aadhaar. Usually reviewed within a few hours.' },
  { title: 'No bank account', badge: 'Empty', badgeTone: 'emp', icon: '🏦', heading: 'Add a bank account', body: 'Payouts and refunds go only to a bank account in your own name.' },
  { title: 'No mandate', badge: 'Empty', badgeTone: 'emp', icon: '🔁', heading: 'Auto-debit not set', body: 'Approve once with your bank; future SIPs then run on their own.' },
  { title: 'No nominee', badge: 'Empty', badgeTone: 'emp', icon: '👥', heading: 'Nominee not added', body: 'Name who inherits these units. You can add up to three people.' },
  { title: 'Pending transaction', badge: 'Loading', badgeTone: 'load', icon: '⏳', heading: 'An order is in flight', body: 'A prior purchase is still with the AMC.' },
];

export const STEP4_FAILURE_STATES: MockState[] = [
  { title: 'Payment failed', badge: 'Error', badgeTone: 'err', icon: '✕', heading: 'Your bank declined it', body: 'No money left your account. If anything was debited it is refunded in 3–5 business days.' },
  { title: 'Validation failed', badge: 'Error', badgeTone: 'err', icon: '!', heading: 'Amount below minimum', body: 'Raise the amount to at least the fund’s minimum to continue.' },
  { title: 'Network lost', badge: 'Error', badgeTone: 'err', icon: '⚡', heading: 'Connection dropped', body: 'Your details are saved. Reconnect and we resume exactly where you stopped.' },
  { title: 'Timeout', badge: 'Error', badgeTone: 'err', icon: '⏱', heading: 'Bank took too long', body: 'We couldn’t confirm your payment in time. Do not pay again until this is checked.' },
  { title: 'Order rejected', badge: 'Error', badgeTone: 'err', icon: '⊘', heading: 'AMC rejected the order', body: 'The scheme has temporarily stopped fresh inflows. Your money is being refunded.' },
  { title: 'Processing', badge: 'Loading', badgeTone: 'load', icon: '◐', heading: 'Confirming with your bank', body: 'Don’t close this window — it usually takes under 20 seconds.' },
];

// ---------------------------------------------------------------------------
// Notifications preview (step 6) — static PREVIEW.
// ---------------------------------------------------------------------------
export function NotificationsPreview() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <div className="flex flex-col gap-2">
        <span className="text-caption font-semibold uppercase tracking-wide text-royal">Push</span>
        <PushCard title="Payment successful" body="Payment received for this fund." time="now" />
        <PushCard title="Order submitted to AMC" body="Sent before today's cut-off." time="16m" />
        <PushCard title="Units allotted" body="Your portfolio is updated." time="1d" />
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-caption font-semibold uppercase tracking-wide text-royal">Email</span>
        <div className="overflow-hidden rounded-md border border-line">
          <div className="bg-navy p-3 text-white">
            <div className="text-small font-medium">Your order is confirmed</div>
            <div className="mt-0.5 text-caption text-white/60">DhanRadar &lt;orders@dhanradar.com&gt;</div>
          </div>
          <div className="p-3 text-caption text-ink-secondary">Order summary and receipt attached as PDF.</div>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-caption font-semibold uppercase tracking-wide text-royal">In-app</span>
        <div className="rounded-md border border-line bg-surface p-3 text-caption text-ink-secondary">
          <b className="text-ink">Units allotted.</b> This fund now shows in your portfolio.
        </div>
        <div className="rounded-md border border-line bg-surface p-3 text-caption text-ink-secondary">
          <b className="text-ink">Slight delay.</b> The AMC is processing a backlog.
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// BSE wire types + defensive-parse helpers shared between InvestWizard.tsx
// (the call sites) and steps.tsx (the render sites).
// ---------------------------------------------------------------------------
export const DEMO_UCC = 'DRTEST009';

export interface BseWebhookEvent {
  event_type: string;
  event: string;
  client_code: string | null;
  order_id: string | null;
  received_at: string | null;
  processed_at: string | null;
}

export interface UccStatusObject {
  [k: string]: unknown;
}

export const UCC_FIELDS: { key: string; name: string; description: string }[] = [
  { key: 'kyc_status', name: 'KYC status', description: 'CVL KRA verification' },
  { key: 'pan_verification', name: 'PAN', description: 'Matched against income-tax records' },
  { key: 'bank_account', name: 'Bank account', description: 'Registered bank verification' },
  { key: 'nominee_2fa', name: 'Nominee / 2FA', description: 'Nominee and two-factor registration' },
  { key: 'transaction_ready', name: 'Transaction ready', description: 'Overall readiness to place an order' },
];

export const STAGE_DEFS: { key: string; name: string }[] = [
  { key: 'received', name: 'Order received by exchange' },
  { key: 'order_2fa_pending', name: 'Awaiting your approval (OTP)' },
  { key: 'payment_pending', name: 'Payment pending' },
  { key: 'exch_init', name: 'Payment gateway initiated' },
];

/** Substring match on event/event_type — BSE's field naming shape isn't
 * pinned down, so this stays defensive rather than an exact-key lookup. */
export function matchesStage(row: BseWebhookEvent, stage: string): boolean {
  return `${row.event ?? ''} ${row.event_type ?? ''}`.toLowerCase().includes(stage);
}

/** Live UAT shape (verified 2026-08-10): kyc_status / pan_verification /
 * nominee_2fa live INSIDE ucc_status_object.holders[0]; bank_account and
 * transaction_ready sit at the top level. Resolve top-level first, then
 * fall back to the first holder. */
export function uccField(so: Record<string, unknown>, key: string): unknown {
  if (so[key] !== undefined) return so[key];
  const holders = so['holders'];
  if (Array.isArray(holders) && holders[0] && typeof holders[0] === 'object') {
    return (holders[0] as Record<string, unknown>)[key];
  }
  return undefined;
}


/** ucc_status_object's per-field shape varies — search its JSON text for
 * TRUE/FALSE rather than assuming a fixed schema (task spec instruction). */
export function toneFromUccValue(v: unknown, isBank: boolean): RowTone {
  const s = JSON.stringify(v ?? '').toUpperCase();
  if (s.includes('TRUE')) return 'ok';
  if (s.includes('FALSE')) return isBank ? 'warn' : 'bad';
  return 'unknown';
}

/** Best-effort extraction of a human-readable error out of an arbitrary BSE
 * response body, so failures can be shown verbatim instead of "[object]". */
export function extractErrorText(body: unknown): string {
  if (typeof body === 'string') return body;
  if (body && typeof body === 'object') {
    const b = body as Record<string, unknown>;
    for (const k of ['message', 'error', 'ErrorMessage', 'Message', 'detail', 'reason']) {
      const v = b[k];
      if (typeof v === 'string' && v.trim()) return v;
    }
  }
  try {
    return JSON.stringify(body);
  } catch {
    return 'Request failed';
  }
}

function PushCard({ title, body, time }: { title: string; body: string; time: string }) {
  return (
    <div className="flex gap-2 rounded-md border border-line bg-surface p-2.5">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-navy text-caption font-bold text-white">D</span>
      <div className="min-w-0 flex-1">
        <div className="text-caption font-semibold text-ink">{title}</div>
        <div className="text-caption text-ink-muted">{body}</div>
      </div>
      <span className="shrink-0 text-micro text-ink-faint">{time}</span>
    </div>
  );
}

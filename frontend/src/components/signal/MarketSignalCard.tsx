'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';

type CardVariant = 'nifty' | 'vix' | 'breadth';

interface ScoreBarProps {
  score: number; // 0–4
  state: 'triggered' | 'watch' | 'no_signal';
}

function ScoreBar({ score, state }: ScoreBarProps) {
  const pct = (score / 4) * 100;
  const fillColor =
    state === 'triggered'
      ? 'bg-emerald'
      : state === 'watch'
      ? 'bg-amber'
      : 'bg-royal';
  return (
    <div className="my-1.5 h-2 w-full overflow-hidden rounded-full border border-line bg-surface-3">
      <div
        className={cn('h-full rounded-full transition-[width] duration-slow ease-out', fillColor)}
        style={{ width: `${pct}%` }}
        role="presentation"
      />
    </div>
  );
}

const NIFTY_LABELS: Record<number, string> = {
  0: 'Strong bullish',
  1: 'Bullish',
  2: 'Neutral',
  3: 'Bearish',
  4: 'Strong correction',
};

const VIX_LABELS: Record<number, string> = {
  0: 'Very low fear',
  1: 'Low fear',
  2: 'Moderate',
  3: 'Elevated',
  4: 'Extreme fear',
};

const BREADTH_LABELS: Record<number, string> = {
  0: 'Broad advance',
  1: 'Mild advance',
  2: 'Mixed',
  3: 'Mild decline',
  4: 'Broad decline',
};

interface MarketSignalCardProps {
  variant: CardVariant;
  score: number; // 0–4
  signalState: 'triggered' | 'watch' | 'no_signal';
  // Nifty props
  niftyValue?: number;
  niftyChangePct?: number;
  niftyThreshold?: number;
  // VIX props
  vixValue?: number;
  vixChangePct?: number;
  vixThreshold?: number;
  // Breadth props
  advances?: number;
  declines?: number;
  adRatio?: number;
  breadthThreshold?: number;
  isLoading?: boolean;
}

const CARD_TITLES: Record<CardVariant, string> = {
  nifty: 'Nifty 50',
  vix: 'India VIX',
  breadth: 'Market Breadth',
};

function numFmt(n: number): string {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n);
}

export function MarketSignalCard({
  variant,
  score,
  signalState,
  niftyValue,
  niftyChangePct,
  niftyThreshold = -8,
  vixValue,
  vixChangePct,
  vixThreshold = 19,
  advances,
  declines,
  adRatio,
  breadthThreshold = 0.8,
  isLoading = false,
}: MarketSignalCardProps) {
  if (isLoading) {
    return (
      <div className="card-pad animate-pulse space-y-2">
        <div className="h-3 w-24 rounded bg-surface-2" />
        <div className="h-6 w-32 rounded bg-surface-2" />
        <div className="h-2 w-full rounded-full bg-surface-2" />
        <div className="h-3 w-16 rounded bg-surface-2" />
      </div>
    );
  }

  const scoreLabel =
    variant === 'nifty'
      ? NIFTY_LABELS[score]
      : variant === 'vix'
      ? VIX_LABELS[score]
      : BREADTH_LABELS[score];

  return (
    <div className="card-pad flex flex-col gap-2">
      {/* Header — factor weight is NEVER rendered (non-neg #2: weights stay server-side) */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
          {CARD_TITLES[variant]}
        </span>
      </div>

      {/* Nifty value block */}
      {variant === 'nifty' && niftyValue != null && (
        <>
          <div className="flex items-baseline gap-2">
            <span className="mono text-[22px] font-semibold text-ink">
              {numFmt(niftyValue)}
            </span>
            {niftyChangePct != null && (
              <span
                className={cn(
                  'mono text-small font-medium',
                  niftyChangePct >= 0 ? 'text-emerald' : 'text-red',
                )}
              >
                {niftyChangePct >= 0 ? '+' : ''}
                {niftyChangePct.toFixed(2)}%
              </span>
            )}
          </div>
          <ScoreBar score={score} state={signalState} />
          {/* Educational band label only — numeric score never reaches the DOM (non-neg #2) */}
          <div className="flex items-center justify-between">
            <span className="text-caption text-ink-muted">{scoreLabel ?? 'Unknown'}</span>
          </div>
          <div className="border-t border-line pt-1">
            <span className="text-caption text-ink-muted">
              Your threshold:{' '}
              <span className="mono font-medium text-ink-secondary">
                {niftyThreshold}%
              </span>
            </span>
          </div>
        </>
      )}

      {/* VIX value block */}
      {variant === 'vix' && vixValue != null && (
        <>
          <div className="flex items-baseline gap-2">
            <span
              className={cn(
                'mono text-[22px] font-semibold',
                vixValue >= vixThreshold ? 'text-amber' : 'text-ink',
              )}
            >
              {vixValue.toFixed(1)}
            </span>
            {vixChangePct != null && (
              <span
                className={cn(
                  'mono text-small font-medium',
                  vixChangePct >= 0 ? 'text-red' : 'text-emerald',
                )}
              >
                {vixChangePct >= 0 ? '+' : ''}
                {vixChangePct.toFixed(1)}%
              </span>
            )}
          </div>
          <ScoreBar score={score} state={signalState} />
          {/* Educational band label only — numeric score never reaches the DOM (non-neg #2) */}
          <div className="flex items-center justify-between">
            <span className="text-caption text-ink-muted">{scoreLabel ?? 'Unknown'}</span>
          </div>
          <div
            className={cn(
              'mt-1 rounded border-l-2 px-2 py-1',
              vixValue >= vixThreshold - 1
                ? 'bg-amber-soft border-l-amber'
                : 'bg-royal-blue-soft border-l-royal',
            )}
          >
            <span className="text-caption text-ink-secondary">
              Your threshold:{' '}
              <span className="mono font-medium">{vixThreshold.toFixed(1)}</span>
            </span>
          </div>
        </>
      )}

      {/* Breadth value block */}
      {variant === 'breadth' && advances != null && declines != null && (
        <>
          <div className="flex items-center gap-4">
            <div>
              <span className="mono text-h3 font-semibold text-emerald tabular-nums">
                {advances}
              </span>
              <span className="ml-1 text-caption text-ink-muted">▲</span>
            </div>
            <div>
              <span className="mono text-h3 font-semibold text-red tabular-nums">
                {declines}
              </span>
              <span className="ml-1 text-caption text-ink-muted">▼</span>
            </div>
            {adRatio != null && (
              <span className="mono ml-auto text-small text-ink-muted">
                A/D {adRatio.toFixed(2)}
              </span>
            )}
          </div>
          <ScoreBar score={score} state={signalState} />
          {/* Educational band label only — numeric score never reaches the DOM (non-neg #2) */}
          <div className="flex items-center justify-between">
            <span className="text-caption text-ink-muted">{scoreLabel ?? 'Unknown'}</span>
          </div>
          <div className="border-t border-line pt-1">
            <span className="text-caption text-ink-muted">
              Your threshold: A/D{' '}
              <span className="mono font-medium text-ink-secondary">
                {breadthThreshold.toFixed(2)}
              </span>
            </span>
          </div>
        </>
      )}
    </div>
  );
}

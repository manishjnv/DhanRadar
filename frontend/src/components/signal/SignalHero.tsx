'use client';

import * as React from 'react';
import { ClipboardCheck } from 'lucide-react';
import { cn } from '@/lib/cn';
import type { SignalState, SignalStateResponse } from '@/features/signal/types';

// SVG score ring: r=28, cx/cy=32, circumference≈175.93
const RING_CIRC = 2 * Math.PI * 28;

function ScoreRing({ fill, color }: { fill: number; color: string }) {
  const offset = RING_CIRC * (1 - Math.min(1, Math.max(0, fill)));
  return (
    <svg width={64} height={64} viewBox="0 0 64 64" aria-hidden="true">
      <circle
        cx={32} cy={32} r={28}
        fill="none" strokeWidth={5}
        className="stroke-line"
      />
      <circle
        cx={32} cy={32} r={28}
        fill="none" strokeWidth={5}
        stroke={color} strokeLinecap="round"
        strokeDasharray={RING_CIRC}
        strokeDashoffset={offset}
        transform="rotate(-90 32 32)"
      />
    </svg>
  );
}

const STATE_CONFIG: Record<
  SignalState,
  {
    label: string;
    ringFill: number;
    badgeClass: string;
    ringColor: string;
    textClass: string;
  }
> = {
  triggered: {
    label: 'Rules triggered',
    ringFill: 1.0,
    badgeClass: 'badge-pos',
    ringColor: 'var(--dr-emerald)',
    textClass: 'text-emerald',
  },
  watch: {
    label: 'Watch — Mixed conditions',
    ringFill: 0.5,
    badgeClass: 'badge-warn',
    ringColor: 'var(--dr-amber)',
    textClass: 'text-amber',
  },
  no_signal: {
    label: 'No rules met',
    ringFill: 0.1,
    badgeClass: 'badge-neutral',
    ringColor: 'var(--text-faint)',
    textClass: 'text-ink-muted',
  },
};

const STATE_BODY: Record<SignalState, string> = {
  triggered:
    'Your configured thresholds are met. Review each signal below.',
  watch:
    'Some conditions are close to your thresholds. Monitor the signals below.',
  no_signal:
    'Market conditions do not meet your configured thresholds today.',
};

const STATE_ICON: Record<SignalState, string> = {
  triggered: '✓',
  watch: '!',
  no_signal: '—',
};

const STATE_BADGE_LABEL: Record<SignalState, string> = {
  triggered: 'HIGH',
  watch: 'MEDIUM',
  no_signal: 'LOW',
};

export interface SignalHeroProps {
  signalState: SignalStateResponse | null;
  isLoading?: boolean;
}

export function SignalHero({ signalState, isLoading = false }: SignalHeroProps) {
  if (isLoading) {
    return (
      <div className="rec animate-pulse">
        <div className="rec-top">
          <div className="h-16 w-16 shrink-0 rounded-full bg-surface-2" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-40 rounded bg-surface-2" />
            <div className="h-3 w-24 rounded bg-surface-2" />
          </div>
        </div>
        <div className="rec-body">
          <div className="h-4 w-full rounded bg-surface-2" />
        </div>
        <div className="rec-foot h-5" />
      </div>
    );
  }

  const state = signalState?.state ?? 'no_signal';
  const cfg = STATE_CONFIG[state];

  return (
    <div className={cn('rec', state === 'triggered' && 'border-emerald/40')}>
      <div className="rec-top">
        {/* Score ring with center icon */}
        <div className="relative shrink-0">
          <ScoreRing fill={cfg.ringFill} color={cfg.ringColor} />
          <span
            className={cn(
              'absolute inset-0 flex items-center justify-center text-caption font-semibold',
              cfg.textClass,
            )}
            aria-hidden="true"
          >
            {STATE_ICON[state]}
          </span>
        </div>

        {/* Label + state badge */}
        <div className="flex flex-col gap-1.5">
          <p className={cn('text-small font-medium', cfg.textClass)}>
            {cfg.label}
          </p>
          <span className={cfg.badgeClass}>{STATE_BADGE_LABEL[state]}</span>
        </div>
      </div>

      {/* Reason body */}
      <div className="rec-body">
        <p className="text-small text-ink-secondary">{STATE_BODY[state]}</p>
      </div>

      {/* SEBI disclosure footer */}
      <div className="rec-foot flex items-center gap-1.5">
        <ClipboardCheck size={12} aria-hidden="true" className="shrink-0" />
        <span>NOT FINANCIAL ADVICE — Based on your own configured thresholds</span>
      </div>
    </div>
  );
}

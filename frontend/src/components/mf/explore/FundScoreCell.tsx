/**
 * FundScoreCell — COMPLIANCE-CRITICAL shared cell.
 *
 * The single source of truth for how a fund's "assessment" renders in the
 * Fund Explorer table AND card grid. Centralising it here keeps the two
 * surfaces in lockstep and means the no-numeric / non-advisory invariants are
 * enforced in exactly one place.
 *
 * Invariants (non-negotiable #1, #2):
 *   - NO numeric score, percentile, grade, or weight ever rendered.
 *   - The ring is decorative: its colour reflects the educational LABEL and its
 *     fill fraction reflects the CONFIDENCE BAND (high/med/low) — never a score.
 *   - When the confidence band is unknown (backend sends null today), the ring
 *     is drawn DASHED so it cannot be misread as a measured value.
 *   - Only the approved label vocabulary is shown (via LabelChip / the map below).
 *   - Advisory verbs (buy/sell/hold/…) can never appear — Label is a closed enum.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

// Label → ring stroke colour. Hex mirrors ScoreRing.LABEL_CONFIG exactly (those
// values are the canonical warm-palette tokens; SVG stroke needs a concrete
// colour, matching the existing compliant precedent in ScoreRing).
const LABEL_STROKE: Record<Label, string> = {
  in_form:           '#00B386',
  on_track:          '#00C2FF',
  off_track:         '#F5A623',
  out_of_form:       '#E5484D',
  insufficient_data: '#6B7280',
};

const LABEL_DISPLAY: Record<Label, string> = {
  in_form:           'In Form',
  on_track:          'On Track',
  off_track:         'Off Track',
  out_of_form:       'Out of Form',
  insufficient_data: 'Insufficient Data',
};

const LABEL_TEXT: Record<Label, string> = {
  in_form:           'text-emerald',
  on_track:          'text-cyan',
  off_track:         'text-amber',
  out_of_form:       'text-red',
  insufficient_data: 'text-ink-muted',
};

// Visual-only fill fraction per band (no numeric meaning). Mirrors ScoreRing.
const BAND_FILL: Record<ConfidenceBand, number> = { high: 0.85, medium: 0.55, low: 0.30 };
const BAND_DISPLAY: Record<ConfidenceBand, string> = { high: 'High', medium: 'Medium', low: 'Low' };

// ---------------------------------------------------------------------------
// Compact ring — label-coloured, band-driven fill, NO centre number.
// ---------------------------------------------------------------------------
function MiniRing({
  label,
  band,
  size = 38,
  stroke = 4,
}: {
  label: Label;
  band: ConfidenceBand | null | undefined;
  size?: number;
  stroke?: number;
}) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const color = LABEL_STROKE[label];
  const frac = band ? BAND_FILL[band] : null;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" focusable="false" className="shrink-0">
      {/* Track */}
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth={stroke} />
      {/* Active arc — solid fraction when band known; dashed full ring when unknown */}
      {frac !== null ? (
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${circ * frac} ${circ * (1 - frac)}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      ) : (
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray="3 4"
          opacity={0.55}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      )}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Factor badge — High / Mid / Low quality signal (never a float).
// ---------------------------------------------------------------------------
const FACTOR_CONFIG = {
  high:   { text: 'text-emerald', label: 'High', aria: 'High'   },
  medium: { text: 'text-amber',   label: 'Mid',  aria: 'Medium' },
  low:    { text: 'text-red',     label: 'Low',  aria: 'Low'    },
} as const;

export function FactorBadge({
  name,
  value,
}: {
  name: string;
  value: 'high' | 'medium' | 'low' | null | undefined;
}) {
  if (!value) {
    return (
      <span className="font-mono text-caption text-ink-muted" aria-label={`${name}: not available`}>
        {name} —
      </span>
    );
  }
  const cfg = FACTOR_CONFIG[value];
  return (
    <span
      aria-label={`${name}: ${cfg.aria}`}
      className={cn(
        'inline-flex items-center gap-1 rounded border border-current px-1.5 py-px',
        'font-mono text-caption font-semibold uppercase tracking-wide',
        cfg.text,
      )}
    >
      <span className="opacity-70">{name}</span>
      {cfg.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Full assessment cell — ring + label word + confidence band word.
// Used by the table "Assessment" column and the card header.
// ---------------------------------------------------------------------------
export interface FundScoreCellProps {
  label: Label;
  confidenceBand: ConfidenceBand | null | undefined;
  /** Ring diameter; defaults to a table-friendly 38px. */
  ringSize?: number;
  /** When true, stack ring above text (card layout) instead of side-by-side. */
  stacked?: boolean;
  className?: string;
}

export function FundScoreCell({
  label,
  confidenceBand,
  ringSize = 38,
  stacked = false,
  className,
}: FundScoreCellProps) {
  const display = LABEL_DISPLAY[label];
  const bandWord = confidenceBand ? BAND_DISPLAY[confidenceBand] : null;
  const aria = bandWord ? `${display}, ${bandWord} confidence` : display;

  return (
    <figure
      className={cn('inline-flex items-center gap-2.5 m-0', stacked && 'flex-col gap-1.5 text-center', className)}
    >
      <MiniRing label={label} band={confidenceBand} size={ringSize} />
      <figcaption className={cn('min-w-0', stacked && 'flex flex-col items-center')}>
        <span className={cn('block text-small font-semibold leading-tight', LABEL_TEXT[label])}>
          {display}
        </span>
        <span className="block font-mono text-caption text-ink-muted leading-tight">
          {bandWord ? `${bandWord} confidence` : 'Confidence n/a'}
        </span>
      </figcaption>
      <span className="sr-only">{aria}</span>
    </figure>
  );
}

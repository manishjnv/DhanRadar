/**
 * ScoreRing — COMPLIANCE-CRITICAL component
 *
 * Architecture rule "No numeric in DOM" (non-negotiable #2):
 *   The public-facing score surface MUST render only the non-advisory
 *   label + confidence BAND. The raw 0–100 numeric score and factor
 *   weights MUST NEVER appear in this component or be passed as props.
 *   Numeric internals are tier-gated server-side (ScorePublic schema vs
 *   Score schema in contracts/openapi.yaml).
 *
 * Label vocabulary (non-negotiable #1):
 *   Only: in_form | on_track | off_track | out_of_form | insufficient_data
 *   NEVER: strong_buy | buy | hold | caution | avoid (advisory verbs banned)
 */

import * as React from 'react';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Types — mirrors openapi.yaml Label + ConfidenceBand enums exactly
// ---------------------------------------------------------------------------
export type Label =
  | 'in_form'
  | 'on_track'
  | 'off_track'
  | 'out_of_form'
  | 'insufficient_data';

export type ConfidenceBand = 'high' | 'medium' | 'low';

export interface ScoreRingProps {
  /** Non-advisory educational label (openapi.yaml Label enum). */
  label: Label;
  /** Confidence band word — never a numeric percentage (non-negotiable #4). */
  confidenceBand: ConfidenceBand;
  /** Accessible label for the SVG. Defaults to derived text. */
  ariaLabel?: string;
  className?: string;
}

// ---------------------------------------------------------------------------
// Colour map — label → warm palette token values
// Maps to the warm palette defined in styles/tokens.json / tailwind.tokens.cjs
// in_form       → emerald  (#00B386 / dark #1FD79A)
// on_track      → cyan     (#00C2FF)
// off_track     → amber    (#F5A623)
// out_of_form   → red      (#E5484D / dark #FF6166)
// insufficient_data → ink-muted (--text-muted, resolved from CSS var)
// ---------------------------------------------------------------------------
const LABEL_CONFIG: Record<
  Label,
  { stroke: string; textClass: string; display: string }
> = {
  in_form:           { stroke: '#00B386', textClass: 'fill-emerald',   display: 'In Form' },
  on_track:          { stroke: '#00C2FF', textClass: 'fill-cyan',      display: 'On Track' },
  off_track:         { stroke: '#F5A623', textClass: 'fill-amber',     display: 'Off Track' },
  out_of_form:       { stroke: '#E5484D', textClass: 'fill-red',       display: 'Out of Form' },
  insufficient_data: { stroke: '#6B7280', textClass: 'fill-ink-muted', display: 'Insufficient Data' },
};

const BAND_DISPLAY: Record<ConfidenceBand, string> = {
  high:   'High confidence',
  medium: 'Medium confidence',
  low:    'Low confidence',
};

// ---------------------------------------------------------------------------
// SVG ring constants
// ---------------------------------------------------------------------------
const SIZE   = 120;
const STROKE = 10;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUM = 2 * Math.PI * RADIUS;

// Ring fill fraction per confidence band (visual only — no numeric meaning)
const BAND_FILL: Record<ConfidenceBand, number> = {
  high:   0.85,
  medium: 0.55,
  low:    0.30,
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function ScoreRing({
  label,
  confidenceBand,
  ariaLabel,
  className,
}: ScoreRingProps) {
  const config   = LABEL_CONFIG[label];
  const fillFrac = BAND_FILL[confidenceBand];
  const dashArr  = `${CIRCUM * fillFrac} ${CIRCUM * (1 - fillFrac)}`;
  const accessibleLabel =
    ariaLabel ?? `${config.display} — ${BAND_DISPLAY[confidenceBand]}`;

  return (
    <figure className={cn('inline-flex flex-col items-center gap-2', className)}>
      {/*
        Single accessible name model (B10): the SVG is decorative (aria-hidden)
        and the figure's name comes from one <figcaption>, avoiding the previous
        triple announcement (figure aria-label + role="img" + sr-only span).
      */}
      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        aria-hidden="true"
        focusable="false"
      >
        {/* Background track */}
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="var(--border)"
          strokeWidth={STROKE}
        />
        {/* Filled arc — colour reflects label (warm palette), length reflects confidence band */}
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke={config.stroke}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={dashArr}
          strokeDashoffset={CIRCUM * 0.25} /* start at 12 o'clock */
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
        {/* Center text — label word only, NO numeric score */}
        <text
          x="50%"
          y="44%"
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="11"
          fontWeight="600"
          letterSpacing="0.04em"
          fill={config.stroke}
        >
          {config.display.toUpperCase()}
        </text>
        {/* Confidence band word — never a numeric % */}
        <text
          x="50%"
          y="62%"
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="9"
          fill="var(--text-muted)"
        >
          {confidenceBand.toUpperCase()}
        </text>
      </svg>

      {/* Accessible caption — the figure's single accessible name. */}
      <figcaption className="sr-only">{accessibleLabel}</figcaption>
    </figure>
  );
}

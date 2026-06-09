/**
 * MoodGauge — COMPLIANCE-CRITICAL component
 *
 * Architecture rule "No numeric in DOM" (non-negotiable #2):
 *   Renders ONLY the regime display word + confidence band word.
 *   ABSOLUTELY NO number, NO percent, NO 0-100 value in this component.
 *
 * Advisory verb ban (non-negotiable #1):
 *   Color mapping is a NON-ADVISORY SYMMETRIC "attention" scale:
 *   both extremes (extreme_fear, extreme_greed) = red (caution).
 *   center (neutral) = cyan (calm).
 *   This deliberately avoids coloring greed as positive/green which
 *   would imply a buy directive — the scale is about intensity of
 *   deviation from neutral, not about direction being good/bad.
 *
 * Accessibility (mirrors ScoreRing pattern):
 *   SVG is aria-hidden decorative; single accessible name via
 *   <figcaption className="sr-only"> on the <figure>.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';

/**
 * Regime domain enum — owned by this shared component (mirrors how ScoreRing
 * owns Label/ConfidenceBand). The mood feature imports Regime from here, so the
 * dependency runs feature → shared, never shared → feature.
 *
 * Educational sentiment read, NOT an advisory signal. The symmetric attention
 * colour scale (see REGIME_COLOR) avoids implying greed = positive/buy.
 */
export type Regime =
  | 'extreme_fear'
  | 'fear'
  | 'neutral'
  | 'greed'
  | 'extreme_greed'
  | 'insufficient_data'
  // Backend sentinel emitted when no snapshot has been computed (data_quality
  // 'unavailable'). The page short-circuits this to a "being computed" empty
  // state, but the gauge must still render it safely if ever passed.
  | 'data_unavailable';

// ---------------------------------------------------------------------------
// Color map — exported for reuse in the history strip on the page
// Symmetric attention scale (see compliance note above):
//   extreme_fear  → red    (#E5484D)
//   fear          → amber  (#F5A623)
//   neutral       → cyan   (#00C2FF)
//   greed         → amber  (#F5A623)
//   extreme_greed → red    (#E5484D)
//   insufficient  → muted  (#6B7280)
// ---------------------------------------------------------------------------
export const REGIME_COLOR: Record<Regime, string> = {
  extreme_fear:      'var(--dr-red)',    // #E5484D — danger/negative token
  fear:              'var(--dr-amber)',  // #F5A623 — warning/attention token
  neutral:           'var(--dr-cyan)',   // #00C2FF — info/calm token
  greed:             'var(--dr-amber)',  // #F5A623 — warning/attention token (symmetric)
  extreme_greed:     'var(--dr-red)',    // #E5484D — danger/negative token (symmetric)
  insufficient_data: 'var(--text-muted)', // #6B7280 light / #7E8699 dark — muted neutral
  data_unavailable:  'var(--text-muted)', // no snapshot computed — muted neutral
};

export const REGIME_DISPLAY: Record<Regime, string> = {
  extreme_fear:      'Extreme Fear',
  fear:              'Fear',
  neutral:           'Neutral',
  greed:             'Greed',
  extreme_greed:     'Extreme Greed',
  insufficient_data: 'Insufficient Data',
  data_unavailable:  'Data Unavailable',
};

// Ordinal position of each regime on the 5-segment arc (left → right).
// Used to place the marker needle; insufficient_data has no valid position.
const REGIME_ORDINAL: Record<Regime, number | null> = {
  extreme_fear:      0,
  fear:              1,
  neutral:           2,
  greed:             3,
  extreme_greed:     4,
  insufficient_data: null,
  data_unavailable:  null,
};

const BAND_DISPLAY: Record<string, string> = {
  high:              'High confidence',
  medium:            'Medium confidence',
  low:               'Low confidence',
  insufficient_data: 'Insufficient data',
};

// ---------------------------------------------------------------------------
// SVG semicircular arc constants
// Viewbox is 200×120; arc sits in the top 100px, label text below.
// ---------------------------------------------------------------------------
const VW      = 200;
const VH      = 120;
const CX      = VW / 2;       // 100
const CY      = 100;          // arc centre Y (at bottom of arc region)
const R       = 80;           // arc radius
const STROKE  = 10;
const NEEDLE_R = 6;           // marker circle radius

// Arc spans from 180° (left) to 0° (right) — a semicircle.
// Angle for ordinal 0..4 mapped linearly over 180° → 0°.
function ordinalToAngleDeg(ordinal: number): number {
  // ordinal 0 = 180° (far left), ordinal 4 = 0° (far right)
  return 180 - (ordinal / 4) * 180;
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return {
    x: cx + r * Math.cos(rad),
    y: cy - r * Math.sin(rad),
  };
}

// Build SVG arc path for the background track (180° → 0°)
function describeSemiArc(cx: number, cy: number, r: number): string {
  const start = polarToCartesian(cx, cy, r, 180);
  const end   = polarToCartesian(cx, cy, r, 0);
  return `M ${start.x} ${start.y} A ${r} ${r} 0 0 1 ${end.x} ${end.y}`;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
export interface MoodGaugeProps {
  regime:          Regime;
  confidenceBand:  string;
  className?:      string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function MoodGauge({ regime, confidenceBand, className }: MoodGaugeProps) {
  // Fail safe on any out-of-enum regime (e.g. a future backend value): fall back
  // to the muted "insufficient" presentation rather than throwing. A thrown
  // error here takes down the whole public /mood page (Next.js error boundary).
  const color        = REGIME_COLOR[regime] ?? REGIME_COLOR.insufficient_data;
  const displayWord  = REGIME_DISPLAY[regime] ?? REGIME_DISPLAY.insufficient_data;
  const bandWord     = BAND_DISPLAY[confidenceBand] ?? confidenceBand;
  // `?? null` (not `|| null`) so ordinal 0 (extreme_fear) is preserved.
  const ordinal      = REGIME_ORDINAL[regime] ?? null;
  const isInsufficient = ordinal === null;
  const trackColor   = isInsufficient ? 'var(--text-muted)' : 'var(--border)';

  const accessibleLabel = `${displayWord} — ${bandWord}`;

  // Needle position
  let needleX = CX;
  let needleY = CY - R;
  if (ordinal !== null) {
    const angleDeg = ordinalToAngleDeg(ordinal);
    const pt       = polarToCartesian(CX, CY, R, angleDeg);
    needleX        = pt.x;
    needleY        = pt.y;
  }

  const arcPath = describeSemiArc(CX, CY, R);

  return (
    <figure className={cn('inline-flex flex-col items-center gap-1', className)}>
      {/*
        aria-hidden: decorative SVG — accessible name comes from <figcaption> below.
        Do NOT add aria-label here (would double-announce per ScoreRing B10 note).
      */}
      <svg
        width={VW}
        height={VH}
        viewBox={`0 0 ${VW} ${VH}`}
        aria-hidden="true"
        focusable="false"
      >
        {/* Background semicircular track */}
        <path
          d={arcPath}
          fill="none"
          stroke={trackColor}
          strokeWidth={STROKE}
          strokeLinecap="round"
          opacity={isInsufficient ? 0.35 : 1}
        />

        {/* Colored active arc — only rendered when we have a valid ordinal position */}
        {ordinal !== null && !isInsufficient && (
          <path
            d={arcPath}
            fill="none"
            stroke={color}
            strokeWidth={STROKE}
            strokeLinecap="round"
            // Mask from left end to needle position using dasharray technique
            strokeDasharray={(() => {
              // Total arc length = π * R
              const totalLen = Math.PI * R;
              // Fraction of arc from left (0°=extreme_greed) to this ordinal
              // ordinal 0 is far-left (180°), ordinal 4 is far-right (0°)
              // We fill from the left (ordinal 0 side) up to this position
              const frac = ordinal / 4;
              return `${totalLen * frac} ${totalLen * (1 - frac)}`;
            })()}
            // Arc starts at left (180°), strokeDasharray fills from there
            strokeDashoffset={0}
          />
        )}

        {/* Needle marker — circle at regime position on the arc */}
        {ordinal !== null && (
          <circle
            cx={needleX}
            cy={needleY}
            r={NEEDLE_R}
            fill={isInsufficient ? 'var(--text-muted)' : color}
            stroke="var(--bg)"
            strokeWidth={2}
          />
        )}

        {/* Regime label word — NO numeric value, regime display word only */}
        <text
          x={CX}
          y={CY + 14}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="15"
          fontWeight="600"
          letterSpacing="0.03em"
          fill={color}
        >
          {displayWord.toUpperCase()}
        </text>

        {/* Confidence band word — never a numeric percentage */}
        <text
          x={CX}
          y={CY + 30}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="10"
          fill="var(--text-muted)"
        >
          {bandWord}
        </text>
      </svg>

      {/* Single accessible name for the figure (mirrors ScoreRing pattern). */}
      <figcaption className="sr-only">{accessibleLabel}</figcaption>
    </figure>
  );
}

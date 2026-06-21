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
 *
 * Visual treatment (decorative only — purely on the aria-hidden SVG):
 *   a soft regime-coloured glow, an arc that draws in on load, and a gentle
 *   pulsing marker. ALL animations are disabled under prefers-reduced-motion
 *   and add no information (the figcaption + words carry the meaning).
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
// SVG semicircular arc constants (~30% larger than the original 200×120 and
// tall enough that the regime + band words sit inside the viewBox with glow room).
// ---------------------------------------------------------------------------
const VW       = 240;        // viewBox width
const VH       = 152;        // viewBox height
const RENDER_W = 260;        // rendered px width (≈30% larger than the old 200)
const RENDER_H = 165;        // rendered px height (keeps the viewBox aspect)
const CX       = VW / 2;     // 120
const CY       = 112;        // arc centre Y
const R        = 94;         // arc radius
const STROKE   = 15;         // arc thickness
const NEEDLE_R = 8;          // marker circle radius
const PULSE_MAX = 24;        // outer radius of the pulsing halo

// Decorative animations — all disabled under prefers-reduced-motion (they carry
// no information; the words + figcaption are the source of truth).
const ANIM_CSS = `
  .mg-arc    { animation: mgDraw 1.15s cubic-bezier(.22,.61,.36,1) both; }
  .mg-needle { animation: mgPop .5s .95s cubic-bezier(.34,1.56,.64,1) both; }
  .mg-pulse  { animation: mgPing 2.6s 1.25s ease-out infinite; }
  .mg-text   { animation: mgFade .6s .85s ease-out both; }
  @keyframes mgDraw { from { stroke-dashoffset: var(--mg-dash); } to { stroke-dashoffset: 0; } }
  @keyframes mgPop  { 0% { r: 0; opacity: 0; } 100% { r: ${NEEDLE_R}px; opacity: 1; } }
  @keyframes mgPing { 0% { r: ${NEEDLE_R}px; opacity: .45; } 70%,100% { r: ${PULSE_MAX}px; opacity: 0; } }
  @keyframes mgFade { from { opacity: 0; } to { opacity: 1; } }
  @media (prefers-reduced-motion: reduce) {
    .mg-arc, .mg-needle, .mg-pulse, .mg-text { animation: none !important; }
    .mg-pulse { opacity: 0; }
  }
`;

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
  // pathLength normalises the arc to 100 units so the dash maths is regime-agnostic.
  const fillUnits = ordinal !== null ? (ordinal / 4) * 100 : 0;

  // Glow + draw-in are inline so they inherit the regime colour. The custom prop
  // `--mg-dash` seeds the draw-in start; base strokeDashoffset 0 = full arc when
  // motion is reduced (no animation).
  const arcStyle = {
    filter: `drop-shadow(0 0 4px ${color})`,
    ['--mg-dash' as string]: String(fillUnits),
  } as React.CSSProperties;
  const needleStyle = { filter: `drop-shadow(0 0 5px ${color})` } as React.CSSProperties;

  return (
    <figure className={cn('inline-flex flex-col items-center gap-1', className)}>
      {/*
        aria-hidden: decorative SVG — accessible name comes from <figcaption> below.
        Do NOT add aria-label here (would double-announce per ScoreRing B10 note).
      */}
      <svg
        width={RENDER_W}
        height={RENDER_H}
        viewBox={`0 0 ${VW} ${VH}`}
        aria-hidden="true"
        focusable="false"
      >
        <style>{ANIM_CSS}</style>

        {/* Background semicircular track */}
        <path
          d={arcPath}
          fill="none"
          stroke={trackColor}
          strokeWidth={STROKE}
          strokeLinecap="round"
          opacity={isInsufficient ? 0.3 : 0.85}
        />

        {/* Colored active arc — only rendered when we have a valid ordinal position.
            Draws in from the left (the extreme_fear side) up to the needle. */}
        {ordinal !== null && !isInsufficient && (
          <path
            className="mg-arc"
            style={arcStyle}
            d={arcPath}
            fill="none"
            stroke={color}
            strokeWidth={STROKE}
            strokeLinecap="round"
            pathLength={100}
            strokeDasharray={`${fillUnits} 100`}
            strokeDashoffset={0}
          />
        )}

        {/* Pulsing halo behind the needle — gentle "alive" radar ping (decorative).
            Hidden entirely when motion is reduced. */}
        {ordinal !== null && !isInsufficient && (
          <circle
            className="mg-pulse"
            cx={needleX}
            cy={needleY}
            r={NEEDLE_R}
            fill={color}
            opacity={0}
          />
        )}

        {/* Needle marker — circle at the regime position on the arc */}
        {ordinal !== null && (
          <circle
            className="mg-needle"
            style={isInsufficient ? undefined : needleStyle}
            cx={needleX}
            cy={needleY}
            r={NEEDLE_R}
            fill={isInsufficient ? 'var(--text-muted)' : color}
            stroke="var(--bg)"
            strokeWidth={2.5}
          />
        )}

        {/* Regime label word — NO numeric value, regime display word only.
            The confidence band is shown in words by ConfidenceExplanation below
            the gauge, so it is not repeated here (it stays in the figcaption for
            screen readers). */}
        <text
          className="mg-text"
          x={CX}
          y={CY + 28}
          textAnchor="middle"
          dominantBaseline="middle"
          fontFamily="Geist Mono, ui-monospace, monospace"
          fontSize="18"
          fontWeight="600"
          letterSpacing="0.1em"
          fill={color}
        >
          {displayWord.toUpperCase()}
        </text>
      </svg>

      {/* Single accessible name for the figure (mirrors ScoreRing pattern). */}
      <figcaption className="sr-only">{accessibleLabel}</figcaption>
    </figure>
  );
}

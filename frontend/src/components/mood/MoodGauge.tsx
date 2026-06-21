/**
 * MoodGauge — COMPLIANCE-CRITICAL component
 *
 * Architecture rule "No numeric in DOM" (non-negotiable #2):
 *   Renders ONLY the regime display word + (server-supplied) confidence band.
 *   ABSOLUTELY NO number, NO percent, NO 0-100 value in this component — the
 *   centre of the dial shows the regime WORD, never a score.
 *
 * Advisory verb ban (non-negotiable #1):
 *   Colour mapping is a NON-ADVISORY SYMMETRIC "attention" scale:
 *   both extremes (extreme_fear, extreme_greed) = red (caution).
 *   center (neutral) = cyan (calm).
 *   The fear→greed ORDER along the dial is descriptive position, not direction:
 *   greed is never coloured green/positive (which would imply a buy directive).
 *
 * Accessibility (mirrors ScoreRing pattern):
 *   SVG is aria-hidden decorative; single accessible name via
 *   <figcaption className="sr-only"> on the <figure>. The visible zone legend
 *   is supplementary.
 *
 * Visual treatment (decorative only, on the aria-hidden SVG): a ~270° dial of
 * five colour zones, a needle to the current zone, a soft regime-coloured glow,
 * an active-zone draw-in, and a gentle pulse. ALL animation is disabled under
 * prefers-reduced-motion and carries no information.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';

/**
 * Regime domain enum — owned by this shared component (mirrors how ScoreRing
 * owns Label/ConfidenceBand). The mood feature imports Regime from here, so the
 * dependency runs feature → shared, never shared → feature.
 */
export type Regime =
  | 'extreme_fear'
  | 'fear'
  | 'neutral'
  | 'greed'
  | 'extreme_greed'
  | 'insufficient_data'
  | 'data_unavailable';

// ---------------------------------------------------------------------------
// Symmetric attention colour scale (see compliance note above).
// ---------------------------------------------------------------------------
export const REGIME_COLOR: Record<Regime, string> = {
  extreme_fear:      'var(--dr-red)',
  fear:              'var(--dr-amber)',
  neutral:           'var(--dr-cyan)',
  greed:             'var(--dr-amber)',
  extreme_greed:     'var(--dr-red)',
  insufficient_data: 'var(--text-muted)',
  data_unavailable:  'var(--text-muted)',
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

// Ordinal position of each regime on the 5-zone dial (left → right).
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

// The five zones, left→right (extreme_fear … extreme_greed). Drives both the
// coloured arc and the legend below the dial.
const ZONES: { regime: Regime; label: string }[] = [
  { regime: 'extreme_fear',  label: 'Extreme Fear' },
  { regime: 'fear',          label: 'Fear' },
  { regime: 'neutral',       label: 'Neutral' },
  { regime: 'greed',         label: 'Greed' },
  { regime: 'extreme_greed', label: 'Extreme Greed' },
];

// ---------------------------------------------------------------------------
// Dial geometry — a 270° arc with a 90° gap at the bottom.
// Angles are compass bearings: 0 = top, 90 = right, 180 = bottom, 270 = left.
// ---------------------------------------------------------------------------
const VW       = 240;
const VH       = 184;
const RENDER_W = 264;
const RENDER_H = 202;
const CX       = 120;
const CY       = 116;
const R        = 92;       // colour-ring centreline radius
const STROKE   = 18;       // ring thickness
const NEEDLE_R = 7;        // hub radius
const NEEDLE_LEN = R - STROKE / 2 - 8;
const START_A  = 225;      // bottom-left
const SWEEP    = 270;      // total dial degrees
const ZPAD     = 0.012;    // gap between zones, in [0,1] dial-fraction units

function pointAt(aDeg: number, r: number): { x: number; y: number } {
  const a = (aDeg * Math.PI) / 180;
  return { x: CX + r * Math.sin(a), y: CY - r * Math.cos(a) };
}

function pToA(p: number): number {
  return START_A + p * SWEEP;
}

// SVG arc path between two dial fractions (clockwise / increasing angle).
function zoneArc(pa: number, pb: number, r: number): string {
  const s = pointAt(pToA(pa), r);
  const e = pointAt(pToA(pb), r);
  const large = (pb - pa) * SWEEP > 180 ? 1 : 0;
  return `M ${s.x.toFixed(2)} ${s.y.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${e.x.toFixed(2)} ${e.y.toFixed(2)}`;
}

// Filled wedge from the hub out to `r`, spanning a dial range — the soft "lit"
// highlight behind the active zone (gives the dial a vibrant spotlight).
function sectorPath(pa: number, pb: number, r: number): string {
  const s = pointAt(pToA(pa), r);
  const e = pointAt(pToA(pb), r);
  const large = (pb - pa) * SWEEP > 180 ? 1 : 0;
  return `M ${CX} ${CY} L ${s.x.toFixed(2)} ${s.y.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${e.x.toFixed(2)} ${e.y.toFixed(2)} Z`;
}

// Decorative animations — all disabled under prefers-reduced-motion.
const ANIM_CSS = `
  .mg-arc    { animation: mgDraw 1.2s cubic-bezier(.22,.61,.36,1) both; }
  .mg-needle { animation: mgFade .5s 1s ease-out both; }
  .mg-pulse  { animation: mgPing 2.6s 1.4s ease-out infinite; }
  .mg-text   { animation: mgFade .6s .85s ease-out both; }
  @keyframes mgDraw { from { stroke-dashoffset: var(--mg-dash); } to { stroke-dashoffset: 0; } }
  @keyframes mgPing { 0% { r: ${NEEDLE_R}px; opacity: .4; } 70%,100% { r: ${NEEDLE_R + 14}px; opacity: 0; } }
  @keyframes mgFade { from { opacity: 0; } to { opacity: 1; } }
  @media (prefers-reduced-motion: reduce) {
    .mg-arc, .mg-needle, .mg-pulse, .mg-text { animation: none !important; }
    .mg-pulse { opacity: 0; }
  }
`;

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
  // Fail safe on any out-of-enum regime: fall back to the muted "insufficient"
  // presentation rather than throwing (a throw would take down the /mood page).
  const color        = REGIME_COLOR[regime] ?? REGIME_COLOR.insufficient_data;
  const displayWord  = REGIME_DISPLAY[regime] ?? REGIME_DISPLAY.insufficient_data;
  const bandWord     = BAND_DISPLAY[confidenceBand] ?? confidenceBand;
  const ordinal      = REGIME_ORDINAL[regime] ?? null;
  const isInsufficient = ordinal === null;
  const accessibleLabel = `${displayWord} — ${bandWord}`;

  // Needle geometry (points at the active zone's centre).
  let needle:
    | { tip: { x: number; y: number }; b1: { x: number; y: number }; b2: { x: number; y: number } }
    | null = null;
  if (ordinal !== null) {
    const midA = pToA((ordinal + 0.5) / 5);
    needle = {
      tip: pointAt(midA, NEEDLE_LEN),
      b1: pointAt(midA + 90, 5),
      b2: pointAt(midA - 90, 5),
    };
  }

  return (
    <figure className={cn('inline-flex flex-col items-center gap-2', className)}>
      <svg
        width={RENDER_W}
        height={RENDER_H}
        viewBox={`0 0 ${VW} ${VH}`}
        aria-hidden="true"
        focusable="false"
      >
        <style>{ANIM_CSS}</style>

        {/* Lit wedge behind the active zone — soft regime-coloured spotlight. */}
        {ordinal !== null && (
          <path
            d={sectorPath(ordinal * 0.2, (ordinal + 1) * 0.2, R + STROKE / 2)}
            fill={color}
            opacity={0.16}
            stroke="none"
          />
        )}

        {/* Five colour zones. The active zone is full + glow + draws in; the rest
            stay vivid-but-subdued so the whole dial reads as a colour scale. */}
        {ZONES.map((z, i) => {
          const zColor = REGIME_COLOR[z.regime];
          const active = ordinal === i;
          const d = zoneArc(i * 0.2 + ZPAD, (i + 1) * 0.2 - ZPAD, R);
          return (
            <path
              key={z.regime}
              className={active ? 'mg-arc' : undefined}
              style={
                active
                  ? ({
                      filter: `drop-shadow(0 0 2px ${zColor}) drop-shadow(0 0 8px ${zColor})`,
                      ['--mg-dash' as string]: '100',
                    } as React.CSSProperties)
                  : undefined
              }
              d={d}
              fill="none"
              stroke={zColor}
              strokeWidth={active ? STROKE + 2 : STROKE}
              strokeLinecap="round"
              opacity={isInsufficient ? 0.4 : active ? 1 : 0.5}
              pathLength={active ? 100 : undefined}
              strokeDasharray={active ? '100' : undefined}
              strokeDashoffset={active ? 0 : undefined}
            />
          );
        })}

        {/* Needle + hub (only when a real regime). */}
        {needle && (
          <g className="mg-needle">
            <circle className="mg-pulse" cx={CX} cy={CY} r={NEEDLE_R} fill={color} opacity={0} />
            <polygon
              points={`${needle.b1.x.toFixed(2)},${needle.b1.y.toFixed(2)} ${needle.tip.x.toFixed(2)},${needle.tip.y.toFixed(2)} ${needle.b2.x.toFixed(2)},${needle.b2.y.toFixed(2)}`}
              fill={color}
              style={{ filter: `drop-shadow(0 0 4px ${color})` }}
            />
            <circle cx={CX} cy={CY} r={NEEDLE_R} fill={color} stroke="var(--bg)" strokeWidth={2.5} />
          </g>
        )}

        {/* Centre regime word — NO numeric value, ever. */}
        <text
          className="mg-text"
          x={CX}
          y={CY + 34}
          textAnchor="middle"
          dominantBaseline="middle"
          fontFamily="Geist Mono, ui-monospace, monospace"
          fontSize="17"
          fontWeight="600"
          letterSpacing="0.08em"
          fill={isInsufficient ? 'var(--text-muted)' : color}
        >
          {displayWord.toUpperCase()}
        </text>
      </svg>

      {/* Zone legend — names the five zones + their colours so the dial is
          self-explanatory (left = fear, right = greed; symmetric attention scale). */}
      <ul className="flex flex-wrap justify-center gap-x-3 gap-y-1" aria-hidden="true">
        {ZONES.map((z) => (
          <li key={z.regime} className="inline-flex items-center gap-1 text-caption text-ink-muted">
            <span
              className="h-2 w-2 rounded-sm"
              style={{ backgroundColor: REGIME_COLOR[z.regime] }}
            />
            {z.label}
          </li>
        ))}
      </ul>

      {/* Single accessible name for the figure (mirrors ScoreRing pattern). */}
      <figcaption className="sr-only">{accessibleLabel}</figcaption>
    </figure>
  );
}

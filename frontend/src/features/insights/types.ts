/**
 * features/insights — TypeScript types for the mood-context endpoint.
 *
 * Mirrors MoodContextResponse backend schema exactly.
 *
 * Compliance:
 *   - No numeric mood_score / 0-100 value in any type (non-neg #2)
 *   - regime is a string union — the shared Regime type from MoodGauge covers the
 *     known values; the hook accepts the full string so new backend values degrade
 *     gracefully rather than failing at parse time (prior RCA: never bare enum lookup)
 *   - observations are backend-authored deterministic strings — rendered verbatim
 *   - disclosure/not_advice/disclaimer_version always present (non-neg #9)
 */

/** Known regime values — mirrors the MoodGauge Regime type + data_unavailable sentinel. */
export type MoodRegime =
  | 'extreme_fear'
  | 'fear'
  | 'neutral'
  | 'greed'
  | 'extreme_greed'
  | 'insufficient_data'
  | 'data_unavailable'
  | (string & {}); // allow unknown future values — safe fallback at render time

/** Banded concentration label — no numeric percentage in DOM (non-neg #2). */
export type ConcentrationBand = 'high' | 'moderate' | 'low' | 'empty' | (string & {});

export interface MoodContextData {
  portfolio_id: string;
  /** Regime string — use REGIME_DISPLAY map for human label; never render raw enum */
  regime: MoodRegime;
  /** ISO date string for the mood snapshot, null when data_unavailable */
  regime_as_of: string | null;
  /** Number of holdings — allowed in DOM (user's own portfolio structure data) */
  fund_count: number;
  /** Banded concentration — not a numeric percentage */
  concentration_band: ConcentrationBand;
  /** Top-category name, null when portfolio is empty */
  top_category: string | null;
  /** Three deterministic backend-authored observation strings — render verbatim */
  observations: string[];
  /** Contextual disclosure (non-neg #9) */
  disclosure: string;
  not_advice: string;
  disclaimer_version: string;
}

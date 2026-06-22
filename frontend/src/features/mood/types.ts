/**
 * Mood feature — TypeScript types.
 * Mirrors the MoodPublic, MoodHistoryItem, and WhyToday backend schemas exactly.
 * No advisory verbs; no numeric score in any type (architecture non-negotiables #1, #2).
 *
 * `Regime` is owned by the shared MoodGauge component (dependency runs
 * feature → shared), mirroring how mf/types imports Label from ScoreRing.
 */
import type { Regime } from '@/components/mood/MoodGauge';

export type { Regime };

export type ConfidenceBand = 'high' | 'medium' | 'low' | 'insufficient_data';

export type DataQuality = 'ok' | 'degraded' | 'unavailable';

// Coarse, non-numeric magnitude tier for a driver factor. The raw contribution /
// weight is proprietary and NEVER sent to the client (non-neg #2) — only this
// 3-way tier string reaches the UI to size the driver bar.
export type MoodFactorTier = 'strong' | 'moderate' | 'slight';

export interface MoodFactor {
  label: string;
  tier:  MoodFactorTier;
}

// Non-numeric trend label derived server-side from the two most recent
// snapshots (ADR-0023 / _compute_trend). The numeric diff is never exposed —
// only this descriptive word reaches the client. `null` when < 2 snapshots.
export type MoodTrend = 'improving' | 'stable' | 'deteriorating';

// ---------------------------------------------------------------------------
// GET /market/mood
// ---------------------------------------------------------------------------
export interface MoodPublic {
  snapshot_date:        string;
  snapshot_at:          string | null;
  regime:               Regime;
  confidence_band:      ConfidenceBand;
  data_quality:         DataQuality;
  contributing_factors: MoodFactor[];
  contradicting_factors: MoodFactor[];
  commentary:           string | null;
  trend:                MoodTrend | null;
  disclosure:           string;
  not_advice:           string;
  disclaimer_version:   string;
}

// ---------------------------------------------------------------------------
// GET /market/mood/history?days=N
// ---------------------------------------------------------------------------
export interface MoodHistoryItem {
  snapshot_date: string;
  regime:        Regime;
}

// ---------------------------------------------------------------------------
// GET /market/flows — FII/DII/PCR public market facts (not computed by DhanRadar)
// DOM-allowed: raw public data, not a proprietary score.
// ---------------------------------------------------------------------------
export interface Flows {
  fii_cr:  number | null;
  dii_cr:  number | null;
  pcr:     number | null;
  as_of:   string | null;
}

// ---------------------------------------------------------------------------
// GET /market/why-today
// ---------------------------------------------------------------------------
export interface WhyToday {
  snapshot_date:        string;
  regime:               Regime;
  commentary:           string | null;
  contributing_factors: string[];
  contradicting_factors: string[];
  disclosure:           string;
  not_advice:           string;
  disclaimer_version:   string;
}

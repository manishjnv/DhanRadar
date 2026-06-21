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

// ---------------------------------------------------------------------------
// GET /market/mood
// ---------------------------------------------------------------------------
export interface MoodPublic {
  snapshot_date:        string;
  snapshot_at:          string | null;
  regime:               Regime;
  confidence_band:      ConfidenceBand;
  data_quality:         DataQuality;
  contributing_factors: string[];
  contradicting_factors: string[];
  commentary:           string | null;
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

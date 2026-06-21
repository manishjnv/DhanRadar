/**
 * ConfidenceExplanation — COMPLIANCE-CRITICAL plain-language reliability note.
 *
 * Sits next to the confidence band word and explains, in one calm non-technical
 * sentence, WHY today's read has the confidence it does — derived purely from
 * the two fields the API already ships: data_quality + confidence_band.
 *
 * Architecture rule "No numeric in DOM" (non-negotiable #2):
 *   Qualitative words only — "some" / "most" / "few" / "mixed". ABSOLUTELY NO
 *   counts ("7 of 11 signals"), NO percentage, NO score. The server-side signal
 *   count / confidence number never reaches this copy.
 *
 * Advisory verb ban (non-negotiable #1):
 *   Explains DATA RELIABILITY only — never what the user should do, never any
 *   "opportunity" / "good time to invest" framing.
 *
 * Safe fallbacks (mirror MoodGauge / MoodContextSection):
 *   Every enum value — including unknown/future values and the unavailable /
 *   insufficient_data sentinels — resolves to a calm sentence. Never throws,
 *   never renders a bare enum key.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';
import type { ConfidenceBand, DataQuality } from '@/features/mood/types';

// Neutral fallback for any combination we don't have a tailored sentence for
// (including unknown/future enum values). Qualitative, non-advisory, no numbers.
const NEUTRAL =
  'Today’s confidence reflects how many market signals were available.';

/**
 * Map (data_quality, confidence_band) → one plain-language sentence.
 * String comparisons (not exhaustive switches) so unknown runtime values are
 * safe rather than throwing — any unmatched input returns NEUTRAL.
 */
export function explainConfidence(
  dataQuality: DataQuality,
  confidenceBand: ConfidenceBand,
): string {
  // Strongest short-circuit: nothing reliable to say.
  if (confidenceBand === 'insufficient_data' || dataQuality === 'unavailable') {
    return 'Too few market signals were available to publish a confident read today.';
  }

  // Missing signals → inherently a lower-confidence read, regardless of band.
  if (dataQuality === 'degraded') {
    return 'Only some market signals were available today, so this is a lower-confidence read.';
  }

  if (dataQuality === 'ok') {
    if (confidenceBand === 'high') {
      return 'Most market signals agreed today, so this is a high-confidence read.';
    }
    if (confidenceBand === 'medium') {
      return 'Market signals were mixed today, so this is a medium-confidence read.';
    }
    if (confidenceBand === 'low') {
      return 'Only some market signals lined up today, so this is a lower-confidence read.';
    }
  }

  return NEUTRAL;
}

export interface ConfidenceExplanationProps {
  dataQuality: DataQuality;
  confidenceBand: ConfidenceBand;
  className?: string;
}

export function ConfidenceExplanation({
  dataQuality,
  confidenceBand,
  className,
}: ConfidenceExplanationProps) {
  return (
    <p
      className={cn('text-small text-ink-secondary', className)}
      data-testid="confidence-explanation"
    >
      {explainConfidence(dataQuality, confidenceBand)}
    </p>
  );
}

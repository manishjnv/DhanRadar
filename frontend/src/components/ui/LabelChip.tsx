/**
 * LabelChip — renders a non-advisory educational label as a coloured chip.
 *
 * Allowed labels: in_form | on_track | off_track | out_of_form | insufficient_data
 * NEVER: strong_buy | buy | hold | caution | avoid
 *
 * Colours mirror ScoreRing's warm-palette mapping.
 */
import * as React from 'react';
import { cn } from '@/lib/cn';
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

const LABEL_DISPLAY: Record<Label, string> = {
  in_form:           'In Form',
  on_track:          'On Track',
  off_track:         'Off Track',
  out_of_form:       'Out of Form',
  insufficient_data: 'Insufficient Data',
};

// Tailwind classes using only canonical token colours.
// Hardcoded hex is intentionally avoided; we use opacity variants of brand tokens.
const LABEL_CLASSES: Record<Label, string> = {
  in_form:           'bg-emerald/10 text-emerald',
  on_track:          'bg-cyan/10 text-cyan',
  off_track:         'bg-amber/10 text-amber',
  out_of_form:       'bg-red/10 text-red',
  insufficient_data: 'bg-surface-2 text-ink-muted',
};

const BAND_DISPLAY: Record<ConfidenceBand, string> = {
  high:   'High',
  medium: 'Medium',
  low:    'Low',
};

export interface LabelChipProps {
  label: Label;
  confidenceBand?: ConfidenceBand;
  className?: string;
}

export function LabelChip({ label, confidenceBand, className }: LabelChipProps) {
  const ariaLabel = confidenceBand
    ? `${LABEL_DISPLAY[label]}, ${BAND_DISPLAY[confidenceBand]} confidence`
    : LABEL_DISPLAY[label];
  return (
    <span
      aria-label={ariaLabel}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-caption font-medium',
        LABEL_CLASSES[label],
        className,
      )}
    >
      {LABEL_DISPLAY[label]}
      {confidenceBand && (
        <span className="opacity-70" aria-hidden="true">· {BAND_DISPLAY[confidenceBand]}</span>
      )}
    </span>
  );
}

/**
 * StatCard — compact "label → value → caption" stat-card primitive.
 *
 * Implements the approved compact / balanced stat-card pattern from the DhanRadar
 * ui-system (docs/ui-system/components/Card.md). Single source of truth for all
 * data stat tiles across the app.
 *
 * Layout:  small muted LABEL (caption, uppercase)
 *          → big VALUE      (h3 scale; Geist Mono + tabular-nums for numbers)
 *          → small CAPTION  (small scale, muted)
 *
 * Compliance: values shown here are the user's own ₹/%/counts (§13 DOM-allowed)
 * or band/word descriptors — never a raw DhanRadar composite score (non-neg #2).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { HelpTip } from '@/components/ui/HelpTip';

export interface StatCardProps {
  /** Small muted label at the top — rendered at caption scale (uppercase). */
  label: React.ReactNode;
  /**
   * The primary display value.
   * • numeric=true (default): Geist Mono + tabular-nums + h3 scale — correct for ₹, %, counts.
   * • numeric=false: body scale + medium weight — correct for text names/words.
   */
  value: React.ReactNode;
  /** Optional secondary line below the value — small scale, ink-secondary. */
  caption?: React.ReactNode;
  /** Optional HelpTip tooltip shown inline with the label. */
  tip?: string;
  /**
   * Whether the value is a number (mono + tabular-nums).
   * Default: true. Pass false when the value is a text name or a band word.
   */
  numeric?: boolean;
  className?: string;
}

export function StatCard({
  label,
  value,
  caption,
  tip,
  numeric = true,
  className,
}: StatCardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-line bg-surface-2 p-4',
        className,
      )}
    >
      {/* LABEL — caption scale, muted, uppercase (via token) */}
      <div className="flex items-center gap-1 text-caption text-ink-muted">
        {label}
        {tip && <HelpTip tip={tip} />}
      </div>

      {/* VALUE — h3 scale; mono + tabular-nums when numeric */}
      <div
        className={cn(
          'mt-1',
          numeric
            ? 'font-mono tabular-nums text-h3 font-medium text-ink'
            : 'text-body font-medium text-ink truncate',
        )}
      >
        {value}
      </div>

      {/* CAPTION — small scale, secondary */}
      {caption !== undefined && caption !== null && (
        <div className="mt-1 text-small text-ink-secondary">{caption}</div>
      )}
    </div>
  );
}

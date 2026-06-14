'use client';

import * as React from 'react';
import { LabelChip } from '@/components/ui/LabelChip';
import { cn } from '@/lib/cn';
import type { MfScheme } from '@/features/mf/types';
import type { Label } from '@/components/charts/ScoreRing';

const LABEL_RANK: Record<Label, number> = {
  in_form: 4,
  on_track: 3,
  off_track: 2,
  out_of_form: 1,
  insufficient_data: 0,
};

interface Props {
  currentValue: number;
  schemes: MfScheme[];
  visible: boolean;
}

export function StickyPortfolioBar({ currentValue, schemes, visible }: Props) {
  // Top label by frequency; ties broken by rank (best label wins).
  const topLabel = React.useMemo<Label | null>(() => {
    if (!schemes.length) return null;
    const counts = new Map<Label, number>();
    for (const s of schemes) counts.set(s.label, (counts.get(s.label) ?? 0) + 1);
    let best: Label | null = null;
    let bestCount = 0;
    for (const [label, count] of counts) {
      if (count > bestCount || (count === bestCount && best !== null && LABEL_RANK[label] > LABEL_RANK[best])) {
        best = label;
        bestCount = count;
      }
    }
    return best;
  }, [schemes]);

  // e.g. "4 on-track · 2 in-form · 1 off-track" (top 3 labels)
  const labelSummary = React.useMemo(() => {
    const counts = new Map<Label, number>();
    for (const s of schemes) counts.set(s.label, (counts.get(s.label) ?? 0) + 1);
    return [...counts.entries()]
      .sort((a, b) => (b[1] - a[1]) || (LABEL_RANK[b[0]] - LABEL_RANK[a[0]]))
      .slice(0, 3)
      .map(([label, count]) => `${count} ${label.replace(/_/g, '-')}`)
      .join(' · ');
  }, [schemes]);

  return (
    <div
      aria-hidden={!visible}
      className={cn(
        // Positioned just below the h-14 topbar; after the md sidebar (w-56).
        'fixed top-14 left-0 md:left-56 right-0 z-30',
        'flex items-center gap-3 px-4 py-2.5',
        'border-b border-line bg-surface/90 backdrop-blur-sm',
        'transition-transform duration-200 ease-in-out',
        visible ? 'translate-y-0' : '-translate-y-full',
      )}
    >
      <span className="shrink-0 text-small font-medium text-ink tabular-nums">
        ₹{currentValue.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
      </span>
      {topLabel && <LabelChip label={topLabel} />}
      <span className="hidden truncate text-caption text-ink-muted sm:block">{labelSummary}</span>
    </div>
  );
}

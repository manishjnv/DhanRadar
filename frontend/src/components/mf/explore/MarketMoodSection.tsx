/**
 * MarketMoodSection — compliant replacement for V4's "DMMI Market Leaders".
 *
 * Wired to the real public GET /market/mood (useMoodCurrent). Renders ONLY:
 *   - the MoodGauge (regime word + confidence band, NO numeric — reused as-is)
 *   - the non-numeric trend word + educational commentary
 *   - the contributing / contradicting MoodFactor lists (label words)
 *   - the mood disclosure bundle (non-negotiable #9)
 *
 * V4's "Suggested SIP action / Suggested lumpsum action" and best/weakest
 * category calls are DROPPED — they are investment advice (non-negotiable #1)
 * and/or have no backing data. Mood describes conditions; it never advises.
 */
'use client';

import * as React from 'react';
import { Skeleton } from '@/components/ui/Skeleton';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { MoodGauge } from '@/components/mood/MoodGauge';
import { useMoodCurrent } from '@/features/mood/api';
import type { MoodFactor, MoodTrend } from '@/features/mood/types';

const TREND_DISPLAY: Record<MoodTrend, { label: string; cls: string }> = {
  improving:     { label: 'Improving', cls: 'text-emerald bg-emerald/10' },
  stable:        { label: 'Stable',    cls: 'text-ink-secondary bg-surface-2' },
  deteriorating: { label: 'Cooling',   cls: 'text-amber bg-amber/10' },
};

function FactorList({ title, items, tone }: { title: string; items: MoodFactor[]; tone: 'up' | 'down' }) {
  if (!items.length) return null;
  return (
    <div>
      <h5 className={tone === 'up' ? 'text-caption font-semibold uppercase tracking-wide text-emerald mb-2' : 'text-caption font-semibold uppercase tracking-wide text-amber mb-2'}>
        {title}
      </h5>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2 text-small text-ink-secondary leading-relaxed">
            <span aria-hidden="true" className={tone === 'up' ? 'text-emerald' : 'text-amber'}>•</span>
            <span className={item.tier === 'strong' ? 'text-ink font-medium' : undefined}>{item.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MarketMoodSection() {
  const { data, isLoading, isError } = useMoodCurrent();

  if (isLoading) {
    return (
      <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">
        <div className="grid gap-6 md:grid-cols-[220px_1fr]">
          <Skeleton className="h-32 rounded-lg" />
          <div className="space-y-3">
            <Skeleton className="h-4 w-3/4 rounded" />
            <Skeleton className="h-4 w-1/2 rounded" />
            <Skeleton className="h-20 rounded" />
          </div>
        </div>
      </div>
    );
  }

  const unavailable =
    isError ||
    !data ||
    data.data_quality === 'unavailable' ||
    data.regime === 'data_unavailable';

  if (unavailable) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-surface-2/50 px-6 py-10 text-center">
        <p className="text-small font-medium text-ink">Market mood is being computed</p>
        <p className="mt-1 text-caption text-ink-muted max-w-md mx-auto">
          The daily mood snapshot updates after market close — check back shortly.
        </p>
      </div>
    );
  }

  const trend = data.trend ? TREND_DISPLAY[data.trend] : null;

  return (
    <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">
      <div className="grid gap-6 md:grid-cols-[220px_1fr] md:items-center">
        <div className="flex flex-col items-center gap-2">
          <MoodGauge regime={data.regime} confidenceBand={data.confidence_band} />
          {trend && (
            <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-caption font-semibold ${trend.cls}`}>
              Trend: {trend.label}
            </span>
          )}
        </div>
        <div>
          {data.commentary && (
            <p className="text-small text-ink-secondary leading-relaxed mb-4">{data.commentary}</p>
          )}
          <div className="grid gap-5 sm:grid-cols-2">
            <FactorList title="Supporting the read" items={data.contributing_factors} tone="up" />
            <FactorList title="Counter-signals" items={data.contradicting_factors} tone="down" />
          </div>
        </div>
      </div>
      <div className="mt-5 border-t border-line pt-4">
        <DisclosureBundle
          disclosure={data.disclosure || undefined}
          notAdvice={data.not_advice || 'Market mood is educational only — not investment advice.'}
        />
      </div>
    </div>
  );
}

'use client';

import * as React from 'react';
import Link from 'next/link';
import { useLearningContent } from '@/features/signal/api';
import type { SignalState } from '@/features/signal/types';

const ICON_COLOR: Record<SignalState, string> = {
  triggered: 'var(--warn)',
  watch:     'var(--info)',
  no_signal: 'var(--positive)',
};

interface LearningContentProps {
  signalState?: SignalState;
}

export function LearningContent({ signalState = 'no_signal' }: LearningContentProps) {
  const { data, isLoading } = useLearningContent(signalState);
  const iconColor = ICON_COLOR[signalState];

  return (
    <div className="card-pad flex flex-col gap-3">
      <p className="text-small font-medium text-ink">Learn</p>
      <ul className="flex flex-col gap-3">
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <li key={i} className="card-pad" style={{ opacity: 0.5 }}>
                <div className="flex items-start gap-3">
                  <div
                    className="h-8 w-8 shrink-0 rounded-md"
                    style={{ background: 'var(--surface-2)' }}
                  />
                  <div className="flex-1 flex flex-col gap-1">
                    <div
                      className="h-3 rounded"
                      style={{ background: 'var(--surface-2)', width: '70%' }}
                    />
                    <div
                      className="h-2 rounded"
                      style={{ background: 'var(--surface-2)', width: '45%' }}
                    />
                  </div>
                </div>
              </li>
            ))
          : (data?.articles ?? []).map((article) => (
              <li key={article.slug}>
                <Link
                  href={article.link}
                  className="flex items-start gap-3 rounded-lg p-2 transition-colors hover:bg-surface-2"
                >
                  <div
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-small"
                    style={{ background: `color-mix(in srgb, ${iconColor} 15%, transparent)`, color: iconColor }}
                    aria-hidden="true"
                  >
                    📖
                  </div>
                  <div className="flex-1">
                    <p className="text-small font-medium text-ink">{article.title}</p>
                  </div>
                  <span className="badge badge-neutral shrink-0">
                    {article.read_min}<span className="mono"> min</span>
                  </span>
                </Link>
              </li>
            ))}
      </ul>
    </div>
  );
}

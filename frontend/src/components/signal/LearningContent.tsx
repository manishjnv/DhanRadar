'use client';

import * as React from 'react';
import Link from 'next/link';
import type { SignalState } from '@/features/signal/types';

interface Article {
  title: string;
  description: string;
  slug: string;
  section: 'concepts' | 'tax';
  minuteRead: number;
  signalTags: SignalState[];
}

const ARTICLES: Article[] = [
  {
    title: 'What is India VIX and why should you care?',
    description: 'Understand how volatility index signals fear in markets.',
    slug: 'india-vix-explained',
    section: 'concepts',
    minuteRead: 4,
    signalTags: ['triggered', 'watch'],
  },
  {
    title: 'Market Breadth — reading advances vs declines',
    description: 'How A/D ratio reveals whether a rally is broad or narrow.',
    slug: 'market-breadth-advances-declines',
    section: 'concepts',
    minuteRead: 5,
    signalTags: ['watch'],
  },
  {
    title: 'SIP discipline — why you should never stop your SIPs',
    description: 'The maths behind staying invested through market corrections.',
    slug: 'sip-discipline',
    section: 'concepts',
    minuteRead: 6,
    signalTags: ['no_signal', 'triggered'],
  },
  {
    title: 'Dip investing strategy — deploying in stages',
    description: 'Staged deployment reduces timing risk and builds discipline.',
    slug: 'staged-dip-investing',
    section: 'concepts',
    minuteRead: 7,
    signalTags: ['triggered', 'watch'],
  },
];

const ICON_BG: Record<SignalState, string> = {
  triggered: 'bg-emerald-soft text-emerald',
  watch: 'bg-amber-soft text-amber',
  no_signal: 'bg-royal-blue-soft text-royal',
};

interface LearningContentProps {
  signalState?: SignalState;
}

export function LearningContent({ signalState = 'no_signal' }: LearningContentProps) {
  const sorted = [...ARTICLES].sort((a, b) => {
    const aMatch = a.signalTags.includes(signalState) ? 0 : 1;
    const bMatch = b.signalTags.includes(signalState) ? 0 : 1;
    return aMatch - bMatch;
  });

  return (
    <div className="card-pad flex flex-col gap-3">
      <p className="text-small font-medium text-ink">Learn</p>
      <ul className="flex flex-col gap-3">
        {sorted.slice(0, 4).map((article) => (
          <li key={article.slug}>
            <Link
              href={`/learn/${article.section}/${article.slug}`}
              className="flex items-start gap-3 rounded-lg p-2 transition-colors hover:bg-surface-2"
            >
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-small ${ICON_BG[signalState]}`}
                aria-hidden="true"
              >
                📖
              </div>
              <div className="flex-1">
                <p className="text-small font-medium text-ink">{article.title}</p>
                <p className="mt-0.5 text-caption text-ink-muted">{article.description}</p>
              </div>
              <span className="badge-neutral shrink-0">{article.minuteRead}m</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

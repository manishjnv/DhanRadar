/**
 * DiscoveryFaq — V4 FAQ accordion, rewritten for compliance.
 *
 * V4's copy described a "0–100 DhanRadar Score" and gave choosing advice — both
 * forbidden. This version explains the EDUCATIONAL labels, confidence bands and
 * ordinal rank, and is explicit that nothing here is investment advice.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';

const FAQ: { q: string; a: string }[] = [
  {
    q: 'What do the fund labels mean?',
    a: 'Each fund carries an educational assessment — In Form, On Track, Off Track, Out of Form, or Insufficient Data. These come from a fixed rule table that reads recent and longer-term behaviour. They describe how a fund has been tracking; they are not buy, sell, or hold advice.',
  },
  {
    q: 'What is the confidence band?',
    a: 'High, Medium, or Low tells you how much data supports the assessment — for example, how long the fund has a track record. It is shown only as a word, never as a precise number.',
  },
  {
    q: 'How is the rank decided?',
    a: 'Within each SEBI category, funds are placed in an ordinal order by a market-wide model that refreshes nightly. The rank is a relative position for comparison inside one category — it is not a recommendation, and ranks are not comparable across different categories.',
  },
  {
    q: 'What returns are shown?',
    a: 'Point-to-point returns based on published NAV over 3 months to 5 years, where enough history exists. Past performance does not guarantee future returns, and returns alone do not capture risk.',
  },
  {
    q: 'How often is this updated?',
    a: 'Assessments, ranks and returns recompute nightly after NAV publication, so the explorer reflects the latest available data each day.',
  },
  {
    q: 'Is any of this investment advice?',
    a: 'No. DhanRadar is an educational research platform, not a SEBI-registered investment adviser. Nothing here is a recommendation to buy, sell, or hold any fund. For decisions specific to you, consult a registered investment adviser and read all scheme documents.',
  },
];

export function DiscoveryFaq() {
  const [open, setOpen] = React.useState<number | null>(0);

  return (
    <div className="rounded-xl border border-line bg-surface px-5 shadow-sm">
      {FAQ.map((item, i) => {
        const isOpen = open === i;
        return (
          <div key={i} className="border-b border-line last:border-0">
            <button
              type="button"
              onClick={() => setOpen(isOpen ? null : i)}
              aria-expanded={isOpen}
              className="w-full flex items-center justify-between gap-3 py-4 text-left text-small font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-royal/40"
            >
              {item.q}
              <span className="text-ink-muted transition-transform shrink-0" style={{ transform: isOpen ? 'rotate(180deg)' : undefined }} aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M6 9 L12 15 L18 9" />
                </svg>
              </span>
            </button>
            <div className={cn('overflow-hidden transition-all', isOpen ? 'pb-4' : 'max-h-0')}>
              {isOpen && <p className="text-small text-ink-secondary leading-relaxed max-w-3xl">{item.a}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

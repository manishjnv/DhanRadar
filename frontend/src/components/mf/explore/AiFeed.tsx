/** S17 "AI Insights Feed" — educational market observations (no directives). */
'use client';
import * as React from 'react';
import { AI_FEED } from './sampleData';

// Render **bold** spans without dangerouslySetInnerHTML.
function renderBold(text: string): React.ReactNode[] {
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) =>
    i % 2 === 1 ? <b key={i} className="text-ink font-semibold">{part}</b> : <React.Fragment key={i}>{part}</React.Fragment>,
  );
}

export function AiFeed() {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {AI_FEED.map((t, i) => (
        <div key={i} className="flex gap-3 rounded-xl border border-line bg-surface p-4 shadow-sm">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-cyan/10 text-cyan shrink-0" aria-hidden="true">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3 L13.5 9 L19 10.5 L13.5 12 L12 18 L10.5 12 L5 10.5 L10.5 9 Z" />
            </svg>
          </span>
          <p className="text-small text-ink-secondary leading-relaxed">{renderBold(t)}</p>
        </div>
      ))}
    </div>
  );
}

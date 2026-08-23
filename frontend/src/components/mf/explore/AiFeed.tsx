/** S11 "AI Insights Feed" — educational market observations (no directives). */
'use client';
import * as React from 'react';
import Link from 'next/link';
import { EmptyState } from '@/components/ui/EmptyState';
import type { LbBoard, LbInsightRow } from '@/features/mf/types';

// Render **bold** spans without dangerouslySetInnerHTML.
function renderBold(text: string): React.ReactNode[] {
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) =>
    i % 2 === 1 ? <b key={i} className="text-ink font-semibold">{part}</b> : <React.Fragment key={i}>{part}</React.Fragment>,
  );
}

function InsightCard({ row }: { row: LbInsightRow }) {
  return (
    <div className="flex gap-3 rounded-xl border border-line bg-surface p-4 shadow-sm">
      <span className="grid h-9 w-9 place-items-center rounded-lg bg-cyan/10 text-cyan shrink-0" aria-hidden="true">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3 L13.5 9 L19 10.5 L13.5 12 L12 18 L10.5 12 L5 10.5 L10.5 9 Z" />
        </svg>
      </span>
      <div className="min-w-0">
        <p className="text-small text-ink-secondary leading-relaxed">{renderBold(row.text)}</p>
        {row.links && row.links.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {row.links.map((l) => (
              <Link key={l.isin} href={`/mf/fund/${l.isin}`}
                className="inline-flex items-center rounded-full border border-line bg-surface-2 px-2.5 py-0.5 text-caption font-medium text-royal hover:bg-royal/10 transition-colors">
                {l.name}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function AiFeed({ board }: { board?: LbBoard<LbInsightRow> }) {
  if (!board) {
    return (
      <EmptyState
        title="Insights not available"
        description="DhanRadar AI insights are refreshed nightly."
      />
    );
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {board.rows.map((row, i) => <InsightCard key={i} row={row} />)}
    </div>
  );
}

/**
 * ExploreSection — shared section chrome for the Fund Explorer page.
 *
 * Ports the V4 numbered-section header (mono index chip + heading + optional
 * tag/info) into Geist/warm tokens, plus a ComingSoonCard used for the V4
 * sections that have NO backing data yet (AI Discovery, Fund Flow, Momentum,
 * Consistency, Low-Cost, AI Insights). We render an honest "in development"
 * state rather than fake values — per the no-fake-data rule.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';

export function SectionHeader({
  index,
  title,
  tag,
  info,
  className,
}: {
  /** Two-digit section index, e.g. "03". */
  index?: string;
  title: string;
  /** Small accent pill (e.g. "Market Mood"). */
  tag?: string;
  /** Muted right-aligned context line (e.g. "684 funds"). */
  info?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center gap-2 mb-3', className)}>
      {index && (
        <span className="font-mono text-caption font-semibold text-royal bg-royal/10 w-6 h-5 rounded-md grid place-items-center shrink-0">
          {index}
        </span>
      )}
      <h2 className="text-h3 font-medium text-ink">{title}</h2>
      {tag && (
        <span className="font-mono text-caption font-semibold uppercase tracking-[0.06em] text-cyan bg-cyan/10 px-2 py-0.5 rounded-full">
          {tag}
        </span>
      )}
      {info && <span className="ml-auto text-caption text-ink-muted">{info}</span>}
    </div>
  );
}

export function ComingSoonCard({
  description,
  icon,
}: {
  description: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-surface-2/50 px-6 py-10 text-center">
      <div className="text-ink-muted mb-2 flex justify-center" aria-hidden="true">
        {icon ?? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 7v5l3 2" />
          </svg>
        )}
      </div>
      <p className="text-small font-medium text-ink">In development</p>
      <p className="mt-1 text-caption text-ink-muted max-w-md mx-auto leading-relaxed">{description}</p>
    </div>
  );
}

/** Vertical rhythm wrapper for each numbered section. */
export function Section({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cn('mt-7', className)}>{children}</section>;
}

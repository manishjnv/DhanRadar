'use client';

/**
 * ConcentrationSection — displays factual portfolio concentration observations.
 *
 * Compliance:
 *   - No advisory verbs ("reduce", "diversify", "rebalance", etc.)
 *   - All text is backend-authored observational copy — rendered verbatim
 *   - disclosure + NOT_ADVICE rendered via <DisclosureBundle> (non-neg #9)
 *   - Empty / cold-start → empty state, not an error
 *   - allocation_pct is user's own portfolio composition data — allowed in DOM
 *   - No numeric DhanRadar score in DOM (non-neg #2)
 */

import * as React from 'react';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { usePortfolioConcentration, type ConcentrationItem } from '@/features/portfolio/api';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function EmptyConcentrationState() {
  return (
    <div className="py-8 text-center text-sm text-text-secondary">
      <p>No concentration data yet.</p>
      <p className="mt-1 text-xs text-text-tertiary">
        Upload your CAS statement to see how your portfolio is distributed.
      </p>
    </div>
  );
}

function AllocationBar({ pct }: { pct: number }) {
  const width = Math.min(Math.max(pct, 0), 100);
  return (
    <div
      className="mt-1 h-1.5 w-full rounded-full bg-surface-secondary"
      role="presentation"
    >
      <div
        className="h-1.5 rounded-full bg-brand-primary"
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

function ConcentrationList({
  title,
  items,
}: {
  title: string;
  items: ConcentrationItem[];
}) {
  return (
    <div className="mt-4">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">
        {title}
      </h4>
      {/* No-suppress rule: keep the heading + show a "no data" line when empty. */}
      {items.length === 0 ? (
        <p className="py-2 text-xs text-text-tertiary">No {title.toLowerCase()} data yet.</p>
      ) : (
      <ul className="divide-y divide-border-subtle">
        {items.map((item) => (
          <li key={item.name} className="py-2">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium text-text-primary">{item.name}</p>
              <span className="shrink-0 text-sm font-semibold tabular-nums text-text-primary">
                {item.allocation_pct.toFixed(1)}%
              </span>
            </div>
            <AllocationBar pct={item.allocation_pct} />
            <p className="mt-1 text-xs text-text-secondary">{item.context}</p>
          </li>
        ))}
      </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

interface ConcentrationSectionProps {
  portfolioId: string;
}

export function ConcentrationSection({ portfolioId }: ConcentrationSectionProps) {
  const { data, isLoading, isError } = usePortfolioConcentration(portfolioId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Portfolio Concentration</CardTitle>
      </CardHeader>
      <CardBody>
        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        )}

        {isError && (
          <p className="text-sm text-status-error" role="alert">
            Unable to load concentration data. Please try again.
          </p>
        )}

        {data && data.data_completeness === 'empty' && <EmptyConcentrationState />}

        {data && data.data_completeness !== 'empty' && (
          <>
            <p className="text-sm text-text-secondary">{data.observation_summary}</p>
            <ConcentrationList title="By Category" items={data.by_category} />
            <ConcentrationList title="By AMC" items={data.by_amc} />
            <ConcentrationList title="By Fund" items={data.by_fund} />
          </>
        )}

        {data && (
          <DisclosureBundle
            disclosure={data.disclosure}
            notAdvice={data.not_advice}
          />
        )}
      </CardBody>
    </Card>
  );
}

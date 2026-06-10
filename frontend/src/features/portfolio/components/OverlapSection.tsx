'use client';

/**
 * OverlapSection — displays factual fund-pair and category-overlap observations.
 *
 * Compliance:
 *   - No advisory verbs ("reduce", "diversify", "switch", etc.)
 *   - All text is backend-authored observational copy — we render it verbatim
 *   - disclosure + NOT_ADVICE rendered via <DisclosureBundle> (non-neg #9)
 *   - Empty / cold-start → empty state, not an error
 *   - No numeric DhanRadar score in DOM (non-neg #2) — overlap_pct is the
 *     user's own portfolio composition data, not a DhanRadar score
 */

import * as React from 'react';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { usePortfolioOverlap, type OverlapResponse } from '@/features/portfolio/api';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function EmptyOverlapState() {
  return (
    <div className="py-8 text-center text-sm text-text-secondary">
      <p>No fund overlap data yet.</p>
      <p className="mt-1 text-xs text-text-tertiary">
        Upload your CAS statement to see how your funds relate to each other.
      </p>
    </div>
  );
}

function CategoryDistributionTable({ data }: { data: OverlapResponse['category_distribution'] }) {
  if (data.length === 0) return null;
  return (
    <div className="mt-4">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">
        Category Distribution
      </h4>
      <ul className="divide-y divide-border-subtle">
        {data.map((item) => (
          <li key={item.category} className="flex items-start gap-3 py-2">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-text-primary">{item.category}</p>
              <p className="mt-0.5 text-xs text-text-secondary">{item.observation}</p>
            </div>
            <div className="shrink-0 text-right">
              <span className="text-sm font-semibold tabular-nums text-text-primary">
                {item.allocation_pct.toFixed(1)}%
              </span>
              <p className="text-xs text-text-tertiary">
                {item.fund_count} {item.fund_count === 1 ? 'fund' : 'funds'}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function FundPairList({ data }: { data: OverlapResponse['fund_pairs'] }) {
  if (data.length === 0) return null;
  return (
    <div className="mt-4">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">
        Same-Category Pairs
      </h4>
      <ul className="divide-y divide-border-subtle">
        {data.map((pair) => (
          <li
            key={`${pair.fund_a_isin}-${pair.fund_b_isin}`}
            className="flex items-start gap-3 py-2"
          >
            <div className="min-w-0 flex-1">
              <p className="text-sm text-text-primary">
                <span className="font-medium">{pair.fund_a_name}</span>
                {' & '}
                <span className="font-medium">{pair.fund_b_name}</span>
              </p>
              <p className="mt-0.5 text-xs text-text-secondary">{pair.observation}</p>
            </div>
            <div className="shrink-0 text-right">
              <span className="text-sm font-semibold tabular-nums text-text-primary">
                {pair.overlap_pct.toFixed(1)}%
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

interface OverlapSectionProps {
  portfolioId: string;
}

export function OverlapSection({ portfolioId }: OverlapSectionProps) {
  const { data, isLoading, isError, error } = usePortfolioOverlap(portfolioId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Fund Category Overlap</CardTitle>
      </CardHeader>
      <CardBody>
        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        )}

        {isError && (
          <p className="text-sm text-status-error" role="alert">
            Unable to load overlap data. Please try again.
          </p>
        )}

        {data && data.data_completeness === 'empty' && <EmptyOverlapState />}

        {data && data.data_completeness !== 'empty' && (
          <>
            <p className="text-sm text-text-secondary">{data.observation_summary}</p>
            <CategoryDistributionTable data={data.category_distribution} />
            <FundPairList data={data.fund_pairs} />
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

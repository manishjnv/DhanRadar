'use client';

/**
 * WhatChangedSection — fetch wrapper that mounts WhatChangedPanel on a page (B62-f2).
 *
 * Compliance:
 *   - All change copy is backend-authored and rendered verbatim by the panel
 *   - disclosure + NOT_ADVICE rendered inside WhatChangedPanel on every data state
 *     (non-neg #9) — this wrapper adds NO second bundle and NO copy of its own
 *   - No numeric DhanRadar score in DOM (non-neg #2) — enforced by the panel
 *   - Empty / cold-start → the panel's calm empty state, not an error
 */

import * as React from 'react';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { WhatChangedPanel } from '@/components/changes';
import { usePortfolioChanges } from '@/features/changes/api';

interface WhatChangedSectionProps {
  portfolioId: string;
}

export function WhatChangedSection({ portfolioId }: WhatChangedSectionProps) {
  const { data, isLoading, isError } = usePortfolioChanges(portfolioId);

  // Transient states keep the Card shell so the section aligns with its
  // siblings while loading; the loaded panel renders its own surface.
  if (isLoading || isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>What Changed</CardTitle>
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
              Unable to load change history. Please try again.
            </p>
          )}
        </CardBody>
      </Card>
    );
  }

  if (!data) return null;

  return <WhatChangedPanel data={data} />;
}

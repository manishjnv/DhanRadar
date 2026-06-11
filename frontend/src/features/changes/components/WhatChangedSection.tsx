'use client';

/**
 * WhatChangedSection — data-fetching wrapper that mounts WhatChangedPanel on the
 * Portfolio Intelligence page (Plan Group 2 / B62-f2). Mirrors OverlapSection /
 * ConcentrationSection.
 *
 * Compliance: WhatChangedPanel renders the disclosure bundle + NOT_ADVICE and its
 * own empty / insufficient_data / "new" states; this wrapper only handles
 * loading + error and passes the backend payload through verbatim. No advisory
 * copy and no numeric score are added here (non-neg #1 / #2).
 */

import * as React from 'react';
import { Skeleton } from '@/components/ui/Skeleton';
import { usePortfolioChanges } from '@/features/changes/api';
import { WhatChangedPanel } from '@/components/changes';

interface WhatChangedSectionProps {
  portfolioId: string;
}

export function WhatChangedSection({ portfolioId }: WhatChangedSectionProps) {
  const { data, isLoading, isError } = usePortfolioChanges(portfolioId);

  if (isLoading) {
    return (
      <div className="space-y-2" data-testid="what-changed-loading">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    );
  }

  if (isError) {
    return (
      <p className="text-sm text-status-error" role="alert">
        Unable to load label-change history. Please try again.
      </p>
    );
  }

  if (!data) return null;

  return <WhatChangedPanel data={data} />;
}

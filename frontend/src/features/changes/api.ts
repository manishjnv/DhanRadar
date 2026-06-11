/**
 * features/changes — TanStack Query hook for portfolio label-change history.
 *
 * Wraps GET /api/v1/portfolio/{portfolioId}/changes
 *
 * Compliance:
 *   - No numeric DhanRadar score in response types (non-neg #2)
 *   - All text is observational — framing helpers live on the backend
 *   - disclosure/not_advice/disclaimer_version must be rendered adjacent to data
 */
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type { PortfolioChangesData } from '@/components/changes/WhatChangedPanel';

// ---------------------------------------------------------------------------
// Types — re-exported from the presentational component so callers have one
// import point for both the hook and the types.
// ---------------------------------------------------------------------------

export type { ChangeKind, FundChange, PortfolioChangesData } from '@/components/changes/WhatChangedPanel';

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function usePortfolioChanges(portfolioId: string) {
  return useQuery({
    queryKey: queryKeys.portfolio.changes(portfolioId),
    queryFn: () => api.get<PortfolioChangesData>(`/portfolio/${portfolioId}/changes`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      // 401/404 are definitional — don't retry
      if (error instanceof ApiError && [401, 404].includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 2 * 60 * 1000,
  });
}

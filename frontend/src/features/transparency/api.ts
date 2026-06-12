/**
 * features/transparency — TanStack Query hook for portfolio transparency data.
 *
 * Wraps GET /api/v1/portfolio/{portfolioId}/transparency
 *
 * Compliance:
 *   - No numeric DhanRadar score in response types (non-neg #2)
 *   - All text is observational — framing helpers live on the backend
 *   - disclosure/not_advice/disclaimer_version must be rendered adjacent to data
 */
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type { PortfolioTransparencyData } from '@/components/transparency';

// ---------------------------------------------------------------------------
// Types — re-exported from the presentational component so callers have one
// import point for both the hook and the types.
// ---------------------------------------------------------------------------

export type {
  PortfolioTransparencyData,
  FundTransparency,
  InsufficientDataRefusal,
  DataSource,
  FreshnessMeta,
} from '@/components/transparency';

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function usePortfolioTransparency(portfolioId: string) {
  return useQuery({
    queryKey: queryKeys.portfolio.transparency(portfolioId),
    queryFn: () => api.get<PortfolioTransparencyData>(`/portfolio/${portfolioId}/transparency`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      // 401/404 are definitional — don't retry
      if (error instanceof ApiError && [401, 404].includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 2 * 60 * 1000,
  });
}

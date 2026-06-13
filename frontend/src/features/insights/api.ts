/**
 * features/insights — TanStack Query hook for portfolio mood-context.
 *
 * Wraps GET /api/v1/portfolio/{portfolioId}/mood-context
 *
 * Compliance:
 *   - No numeric DhanRadar score in response types (non-neg #2)
 *   - All observation text is backend-authored and deterministic — never LLM
 *   - disclosure/not_advice/disclaimer_version must be rendered adjacent to data
 *   - Auth: cookie RS256 JWT only — never an Authorization header (non-neg #5)
 */
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type { MoodContextData } from './types';

export type { MoodContextData, MoodRegime, ConcentrationBand } from './types';

export function usePortfolioMoodContext(portfolioId: string) {
  return useQuery({
    queryKey: queryKeys.portfolio.moodContext(portfolioId),
    queryFn: () => api.get<MoodContextData>(`/portfolio/${portfolioId}/mood-context`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      // 401/404 are definitional — don't retry
      if (error instanceof ApiError && [401, 404].includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 2 * 60 * 1000,
  });
}

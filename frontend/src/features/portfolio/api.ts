/**
 * Portfolio Intelligence feature — TanStack Query hooks.
 *
 * Wraps GET /api/v1/portfolio/{portfolioId}/overlap
 * and GET /api/v1/portfolio/{portfolioId}/concentration
 *
 * Compliance:
 *   - No numeric DhanRadar score in response types (non-neg #2)
 *   - All text is observational — framing helpers live on the backend
 *   - disclosure/not_advice/disclaimer_version must be rendered adjacent to data
 */
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';

// ---------------------------------------------------------------------------
// Overlap types
// ---------------------------------------------------------------------------

export interface FundPairOverlap {
  fund_a_isin: string;
  fund_a_name: string;
  fund_b_isin: string;
  fund_b_name: string;
  /** Factual % of shared category allocation — user's own data, allowed in DOM */
  overlap_pct: number;
  /** Backend-authored observational text — NEVER advisory */
  observation: string;
}

export interface CategoryOverlap {
  category: string;
  /** Factual allocation % — allowed in DOM */
  allocation_pct: number;
  fund_count: number;
  observation: string;
}

export interface OverlapResponse {
  portfolio_id: string;
  as_of_date: string | null;
  fund_pairs: FundPairOverlap[];
  category_distribution: CategoryOverlap[];
  observation_summary: string;
  data_completeness: 'empty' | 'partial' | 'complete';
  disclosure: string;
  not_advice: string;
  disclaimer_version: string;
}

// ---------------------------------------------------------------------------
// Concentration types
// ---------------------------------------------------------------------------

export interface ConcentrationItem {
  name: string;
  /** Factual allocation % — allowed in DOM */
  allocation_pct: number;
  /** Backend-authored educational context — NEVER advisory */
  context: string;
}

export interface ConcentrationResponse {
  portfolio_id: string;
  as_of_date: string | null;
  by_category: ConcentrationItem[];
  by_amc: ConcentrationItem[];
  by_fund: ConcentrationItem[];
  observation_summary: string;
  data_completeness: 'empty' | 'partial' | 'complete';
  disclosure: string;
  not_advice: string;
  disclaimer_version: string;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function usePortfolioOverlap(portfolioId: string) {
  return useQuery({
    queryKey: queryKeys.portfolio.overlap(portfolioId),
    queryFn: () => api.get<OverlapResponse>(`/portfolio/${portfolioId}/overlap`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      // 401/404 are definitional — don't retry
      if (error instanceof ApiError && [401, 404].includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 2 * 60 * 1000,
  });
}

export function usePortfolioConcentration(portfolioId: string) {
  return useQuery({
    queryKey: queryKeys.portfolio.concentration(portfolioId),
    queryFn: () => api.get<ConcentrationResponse>(`/portfolio/${portfolioId}/concentration`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      if (error instanceof ApiError && [401, 404].includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 2 * 60 * 1000,
  });
}

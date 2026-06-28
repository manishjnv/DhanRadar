/**
 * Portfolio Intelligence feature — TanStack Query hooks.
 *
 * Wraps:
 *   GET /api/v1/portfolio/{portfolioId}/overlap
 *   GET /api/v1/portfolio/{portfolioId}/concentration
 *   GET /api/v1/portfolio/{portfolioId}/holdings   (DataEnvelope)
 *   GET /api/v1/portfolio/{portfolioId}/summary    (DataEnvelope)
 *
 * Compliance:
 *   - No numeric DhanRadar score in response types (non-neg #2)
 *   - All text is observational — framing helpers live on the backend
 *   - disclosure/not_advice/disclaimer_version must be rendered adjacent to data
 */
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type { DataEnvelope } from '@/data/envelope';

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

// ---------------------------------------------------------------------------
// Holdings types (DataEnvelope)
// ---------------------------------------------------------------------------

/** Educational status label from the scoring engine — educational verb set only, never advisory. */
export type EducationalLabel =
  | 'in_form'
  | 'on_track'
  | 'off_track'
  | 'out_of_form'
  | 'insufficient_data';

export interface Holding {
  isin: string;
  scheme_name: string;
  category: string | null;
  folio_number: string;
  /** User's own factual units — allowed in DOM */
  units: number;
  /** User's own invested amount — allowed in DOM */
  invested_amount: number | null;
  /** User's own current value — allowed in DOM */
  current_value: number;
  current_nav: number | null;
  /** Educational label — not an advisory verb */
  label: EducationalLabel | null;
  /** Data-confidence band — not a score or verdict */
  confidence_band: 'high' | 'medium' | 'low' | null;
  as_of: string | null;
}

export interface HoldingsPayload {
  portfolio_id: string;
  holdings: Holding[];
}

// ---------------------------------------------------------------------------
// Summary types (DataEnvelope)
// ---------------------------------------------------------------------------

export interface SummaryPayload {
  portfolio_id: string;
  /** User's own total portfolio value — allowed in DOM */
  total_value: number;
  /** User's own total invested — allowed in DOM */
  total_invested: number;
  /** User's own absolute gain — allowed in DOM */
  gain: number;
  /** User's own gain % — allowed in DOM */
  gain_pct: number;
  /** User's own XIRR — allowed in DOM */
  xirr_pct: number | null;
  fund_count: number;
  funds_scored: number;
  /** Data-confidence band for the portfolio as a whole — a data-quality descriptor, NOT a verdict */
  confidence_band: 'high' | 'medium' | 'low' | null;
  as_of: string | null;
}

// ---------------------------------------------------------------------------
// Hooks — DataEnvelope variants
// ---------------------------------------------------------------------------

const SKIP_RETRY = [401, 404];

export function usePortfolioHoldings(portfolioId: string) {
  return useQuery<DataEnvelope<HoldingsPayload>>({
    queryKey: queryKeys.portfolio.holdings(portfolioId),
    queryFn: () => api.get<DataEnvelope<HoldingsPayload>>(`/portfolio/${portfolioId}/holdings`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      if (error instanceof ApiError && SKIP_RETRY.includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function usePortfolioSummaryById(portfolioId: string) {
  return useQuery<DataEnvelope<SummaryPayload>>({
    queryKey: queryKeys.portfolio.summaryById(portfolioId),
    queryFn: () => api.get<DataEnvelope<SummaryPayload>>(`/portfolio/${portfolioId}/summary`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      if (error instanceof ApiError && SKIP_RETRY.includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 5 * 60 * 1000,
  });
}

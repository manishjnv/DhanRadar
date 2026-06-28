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

// ---------------------------------------------------------------------------
// Risk types (DataEnvelope) — standard financial ratios, DOM-allowed.
// Compliance: no numeric DhanRadar composite/score in either type (non-neg #2).
// ---------------------------------------------------------------------------

/**
 * Standard risk payload returned by GET /portfolio/{id}/risk.
 * `risk_band` is a factual descriptor ("moderate" / "high") — never an advisory verb.
 * `recovery_months` is always null server-side (feature not built yet).
 */
export interface RiskPayload {
  portfolio_id: string;
  /** Risk band — factual descriptor, never advisory verb */
  risk_band: 'low' | 'moderate' | 'high' | 'very_high' | null;
  /** Standard volatility metric — DOM-allowed standard ratio */
  volatility_pct: number | null;
  /** Standard max-drawdown metric — DOM-allowed standard ratio */
  max_drawdown_pct: number | null;
  /** Always null server-side — render as "coming soon" */
  recovery_months: null;
  fund_count: number;
  funds_with_metrics: number;
  as_of: string | null;
}

/**
 * Advanced risk payload returned by GET /portfolio/{id}/risk?advanced=true.
 * Requires Plus tier; free users get HTTP 402.
 * `alpha`/`beta` are always null server-side (not built yet).
 */
export interface RiskAdvancedPayload {
  portfolio_id: string;
  /** Standard Sharpe ratio — DOM-allowed */
  sharpe_ratio: number | null;
  /** Standard Sortino ratio — DOM-allowed */
  sortino_ratio: number | null;
  /** Rolling 1-year average return % — DOM-allowed */
  rolling_1y_avg_pct: number | null;
  /** % of rolling 1Y windows that were positive — DOM-allowed */
  rolling_1y_pct_positive: number | null;
  /** Always null server-side */
  alpha: null;
  /** Always null server-side */
  beta: null;
  as_of: string | null;
}

const SKIP_RETRY_WITH_402 = [401, 402, 404];

export function usePortfolioRisk(portfolioId: string) {
  return useQuery<DataEnvelope<RiskPayload>>({
    queryKey: queryKeys.portfolio.risk(portfolioId),
    queryFn: () => api.get<DataEnvelope<RiskPayload>>(`/portfolio/${portfolioId}/risk`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      if (error instanceof ApiError && SKIP_RETRY.includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Advanced risk hook — free users receive HTTP 402; the component reads
 * `isError` + the thrown ApiError.problem.status to render the upgrade card.
 * `enabled` defaults to true; pass false to defer until user expands the panel.
 */
export function usePortfolioRiskAdvanced(portfolioId: string, enabled = true) {
  return useQuery<DataEnvelope<RiskAdvancedPayload>>({
    queryKey: queryKeys.portfolio.riskAdvanced(portfolioId),
    queryFn: () =>
      api.get<DataEnvelope<RiskAdvancedPayload>>(`/portfolio/${portfolioId}/risk?advanced=true`),
    enabled: !!portfolioId && enabled,
    // 402 is a tier gate — never retry, treat like 401/404
    retry: (count, error) => {
      if (error instanceof ApiError && SKIP_RETRY_WITH_402.includes(error.problem.status))
        return false;
      return count < 1;
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Portfolio Intelligence feature — TanStack Query hooks.
 *
 * Wraps:
 *   GET /api/v1/portfolio/{portfolioId}/allocation?by=category|amc  (DataEnvelope)
 *   GET /api/v1/portfolio/{portfolioId}/concentration              (DataEnvelope)
 *   GET /api/v1/portfolio/{portfolioId}/diversification            (DataEnvelope)
 *   GET /api/v1/portfolio/{portfolioId}/holdings                   (DataEnvelope)
 *   GET /api/v1/portfolio/{portfolioId}/summary                    (DataEnvelope)
 *   GET /api/v1/portfolio/{portfolioId}/risk                       (DataEnvelope)
 *
 * Compliance:
 *   - No numeric DhanRadar composite score in response types (non-neg #2).
 *     value/weight_pct/counts are the user's OWN figures — DOM-allowed.
 *   - `band` is a factual descriptor word, never a number.
 */
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type { DataEnvelope } from '@/data/envelope';

const SKIP_RETRY = [401, 404];

// ---------------------------------------------------------------------------
// Allocation types (DataEnvelope) — user's own ₹/% breakdown, DOM-allowed.
// ---------------------------------------------------------------------------

export interface AllocationBucket {
  bucket: string;
  /** User's own value in this bucket — DOM-allowed */
  value: number;
  /** User's own % weight of this bucket — DOM-allowed */
  weight_pct: number;
}

export interface AllocationData {
  portfolio_id: string;
  by: string;
  buckets: AllocationBucket[];
  total_value: number;
  fund_count: number;
  as_of: string | null;
}

// ---------------------------------------------------------------------------
// Concentration types (DataEnvelope) — factual descriptor band + user's own %.
// ---------------------------------------------------------------------------

export interface NamedWeight {
  name: string;
  /** User's own % weight — DOM-allowed */
  weight_pct: number;
}

export interface ConcentrationData {
  portfolio_id: string;
  /** Factual descriptor word, never a number (non-neg #2) */
  band: 'low' | 'moderate' | 'high' | 'very_high' | null;
  top_fund: NamedWeight | null;
  top_amc: NamedWeight | null;
  by_amc: NamedWeight[];
  fund_count: number;
  amc_count: number;
  as_of: string | null;
}

// ---------------------------------------------------------------------------
// Diversification types (DataEnvelope) — factual descriptor band + user's own facts.
// ---------------------------------------------------------------------------

export interface DiversificationData {
  portfolio_id: string;
  /** Factual descriptor word; high = well-spread (non-neg #2) */
  band: 'low' | 'medium' | 'high' | null;
  category_count: number;
  top_category: string | null;
  top_category_pct: number | null;
  fund_count: number;
  as_of: string | null;
}

// ---------------------------------------------------------------------------
// Hooks — allocation / concentration / diversification (DataEnvelope)
// ---------------------------------------------------------------------------

export function usePortfolioAllocation(portfolioId: string, by: 'category' | 'amc' = 'category') {
  return useQuery<DataEnvelope<AllocationData>>({
    queryKey: queryKeys.portfolio.allocation(portfolioId, by),
    queryFn: () => api.get<DataEnvelope<AllocationData>>(`/portfolio/${portfolioId}/allocation?by=${by}`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      if (error instanceof ApiError && SKIP_RETRY.includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function usePortfolioConcentration(portfolioId: string) {
  return useQuery<DataEnvelope<ConcentrationData>>({
    queryKey: queryKeys.portfolio.concentration(portfolioId),
    queryFn: () => api.get<DataEnvelope<ConcentrationData>>(`/portfolio/${portfolioId}/concentration`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      if (error instanceof ApiError && SKIP_RETRY.includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function usePortfolioDiversification(portfolioId: string) {
  return useQuery<DataEnvelope<DiversificationData>>({
    queryKey: queryKeys.portfolio.diversification(portfolioId),
    queryFn: () => api.get<DataEnvelope<DiversificationData>>(`/portfolio/${portfolioId}/diversification`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      if (error instanceof ApiError && SKIP_RETRY.includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 5 * 60 * 1000,
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
  /** User's own gain % — allowed in DOM; null when total_invested is 0 (no holdings yet) */
  gain_pct: number | null;
  /** User's own XIRR — allowed in DOM */
  xirr_pct: number | null;
  /** User's own 1-day value change, flow-adjusted — allowed in DOM; null until ≥2 daily-valuation rows exist (M2.2) */
  day_change?: number | null;
  /** Day change % from the SAME two valuation rows as day_change — never recomputed client-side */
  day_change_pct?: number | null;
  fund_count: number;
  funds_scored: number;
  /** Data-confidence band for the portfolio as a whole — a data-quality descriptor, NOT a verdict */
  confidence_band: 'high' | 'medium' | 'low' | null;
  as_of: string | null;
}

// ---------------------------------------------------------------------------
// Hooks — DataEnvelope variants
// ---------------------------------------------------------------------------

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
  /** Risk band — INDICATIVE factual descriptor (from avg fund volatility, B88), never advisory verb */
  risk_band: 'low' | 'moderate' | 'high' | 'very_high' | null;
  /** What the indicative band is based on, e.g. "average fund volatility" (B88) */
  risk_band_basis: string | null;
  /** Average annualised volatility of the funds — indicative, not the true portfolio σ (B88) */
  volatility_pct: number | null;
  /** Deferred (B88) — portfolio drawdown needs the valuation series; null → "coming soon" */
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

const SKIP_RETRY_WITH_402 = [401, 402, 404]; // never retry — 402 is the tier-gate, distinct from an OpenRouter balance 402

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

// ---------------------------------------------------------------------------
// Value-series types (DataEnvelope) — daily portfolio value snapshots, M2.2.
// All values are the user's own calculated ₹ — DOM-allowed (#2-exempt user money).
// ---------------------------------------------------------------------------

export interface ValueSeriesPoint {
  /** ISO date string (YYYY-MM-DD) */
  date: string;
  /** User's own total portfolio value on this date — allowed in DOM */
  value: number;
  /** User's own total invested on this date — allowed in DOM */
  invested: number;
}

export interface ValueSeriesPayload {
  portfolio_id: string;
  point_count: number;
  /** All available daily data points, ordered ascending by date. Empty on cold-start. */
  points: ValueSeriesPoint[];
}

/**
 * Hook for the full daily portfolio-value series (all available rows, no period cap).
 * Returns an empty `points` array on cold-start (M2.2 data starts 2026-07-01, forward-only).
 * The front-end windows the data for the chart/sparkline — no `days` param needed.
 */
/**
 * Calls the existing M2.2 /valuation-series endpoint with ?days=1095 (the full
 * available window). The FE windows locally for the chart/sparkline.
 */
export function usePortfolioValueSeries(portfolioId: string) {
  return useQuery<DataEnvelope<ValueSeriesPayload>>({
    queryKey: queryKeys.portfolio.valueSeries(portfolioId),
    queryFn: () =>
      api.get<DataEnvelope<ValueSeriesPayload>>(`/portfolio/${portfolioId}/valuation-series?days=1095`),
    enabled: !!portfolioId,
    retry: (count, error) => {
      if (error instanceof ApiError && SKIP_RETRY.includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 5 * 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Nifty 50 benchmark close series (public reference data — no auth required).
// DOM-allowed: Nifty 50 price closes are public market facts.
// Disclosure: price index only — excludes dividends (ADR-0037 part b).
// ---------------------------------------------------------------------------

export interface NiftyClosePoint {
  /** ISO date string (YYYY-MM-DD) */
  close_date: string;
  /** Nifty 50 price-index closing level on this date — public market fact, DOM-allowed */
  close_value: number;
}

export interface NiftyCloseSeriesPayload {
  benchmark: string;
  /** "Nifty 50 price index · excludes dividends" */
  disclosure: string;
  point_count: number;
  /** All available daily close points, ordered ascending by date. Empty on cold-start. */
  points: NiftyClosePoint[];
}

/**
 * Nifty 50 price-index daily close series from GET /mf/benchmark/nifty50.
 * Public endpoint — no auth needed. Optional from/to ISO date filters.
 * Empty points on cold-start (before the historical backfill runs on deploy).
 */
export function useNiftyCloseSeries(params?: { from?: string; to?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.from) searchParams.set('from', params.from);
  if (params?.to) searchParams.set('to', params.to);
  const qs = searchParams.toString();
  return useQuery<NiftyCloseSeriesPayload>({
    queryKey: queryKeys.benchmark.nifty50(params),
    queryFn: () =>
      api.get<NiftyCloseSeriesPayload>(`/mf/benchmark/nifty50${qs ? `?${qs}` : ''}`),
    retry: (count, error) => {
      if (error instanceof ApiError && SKIP_RETRY.includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 10 * 60 * 1000, // closes change only once a day
  });
}

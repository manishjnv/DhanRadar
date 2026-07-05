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
  /** User's own per-fund XIRR (M2.3, ledger-derived) — allowed in DOM; null when the ledger has no history for this holding (honest, never fabricated) */
  xirr_pct?: number | null;
  /** User's own today's ₹ move for this fund (CAMS-parity) — allowed in DOM; null until 2 recent NAV dates exist */
  day_change?: number | null;
  /** Day change % from the SAME NAV pair as day_change; null with it */
  day_change_pct?: number | null;
  /**
   * ADR-0039 (P1) — per-holding data-integrity tag: 'ledger_backed' (normal) | 'stated_only'
   * (holdings-only source, no transaction history) | 'unpriced' (no live NAV) | 'placeholder'
   * (unresolved ISIN). A data-quality fact, never a score (#2-exempt). This route never upgrades
   * 'ledger_backed' → 'stated_only' (that only happens on /summary) — see portfolio_read.py.
   */
  data_state?: 'ledger_backed' | 'stated_only' | 'unpriced' | 'placeholder' | null;
  /**
   * ELSS/tax-saver per-lot lock-in block (P2, net new, 2026-07-06) — present ONLY for holdings
   * whose category is the ELSS canonical leaf; `null` for every other holding (not an empty
   * state, the block simply doesn't apply). `approximate` is honest-uncertainty, never a wrong
   * precise number: true when a redemption's units couldn't be cleanly attributed to specific
   * lots (the ledger doesn't cover the whole holding history).
   */
  lockin?: {
    lots: Array<{
      /** ISO date the lot opened (a BUY-type transaction). */
      txn_date: string;
      /** Units still open in this lot after any FIFO redemptions consumed earlier lots. */
      units: number;
      /** ISO date this lot's 3-year SEBI lock-in ends. */
      lock_until: string;
      locked: boolean;
    }>;
    locked_units: number;
    free_units: number;
    /** ISO date of the soonest-unlocking still-locked lot; null when nothing is locked. */
    next_unlock_date: string | null;
    /** True when a redemption's units couldn't be cleanly FIFO-attributed to specific lots —
     * the figures above are a best-effort remainder, not a claimed-precise number. */
    approximate: boolean;
  } | null;
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
  /**
   * ADR-0039 — the integer % of total_value carried by holdings priced off a LIVE nav (as opposed
   * to a stale/no-NAV holding's cost_fallback). null once it rounds to 100% (nothing to caveat).
   */
  value_priced_pct?: number | null;
  /** User's own total invested — allowed in DOM */
  total_invested: number;
  /**
   * ADR-0039 — count of active holdings with no positive invested amount (a holdings-only source
   * that never captured cost). 0 when none are missing.
   */
  invested_missing_count?: number;
  /** User's own absolute gain — allowed in DOM */
  gain: number;
  /** User's own gain % — allowed in DOM; null when total_invested is 0 (no holdings yet) */
  gain_pct: number | null;
  /** CAMS-comparable "Cost value" = total_invested + reinvested-IDCW cost — allowed in DOM */
  cost_value?: number;
  /** User's own gain vs cost_value (instead of cash-basis total_invested) — allowed in DOM */
  gain_vs_cost?: number;
  /** gain_vs_cost as a %; null when cost_value is 0 */
  gain_vs_cost_pct?: number | null;
  /** User's own ledger-based lifetime XIRR (CAMS-parity) — over ACTIVE holdings only; allowed in DOM */
  xirr_pct: number | null;
  /**
   * Share of total_value (%) that xirr_pct's ledger flows actually cover (Fix 2b, 2026-07-04) —
   * null when coverage is full (>= ~99%) or there's no xirr_pct at all. A ledger-less holding (a
   * holdings-only source, e.g. a KFin consolidated PDF with no transaction history) can leave the
   * lifetime XIRR covering only PART of the portfolio's value; when that happens this names the
   * honest share so the UI can caveat the XIRR chip instead of implying it covers everything.
   */
  xirr_coverage_pct?: number | null;
  /** User's own windowed (~1-year) XIRR (M2.3) — allowed in DOM; null on cold-start or a too-short window */
  xirr_1y_pct?: number | null;
  /** Actual days the xirr_1y_pct window covers — may be < 365 when the series is younger; only label it "1Y" when >= 360 */
  xirr_1y_window_days?: number | null;
  /** User's own 1-day value change, bottom-up (units × NAV move, §39.1) — allowed in DOM; null until a holding has two NAV dates */
  day_change?: number | null;
  /** Day change % from the SAME NAV pairs as day_change — never recomputed client-side */
  day_change_pct?: number | null;
  /**
   * ISO date (YYYY-MM-DD) day_change/day_change_pct are anchored to (2026-07-04) — during AMFI's
   * staggered ~23:30 IST NAV ingest, a fund still one day behind is excluded rather than blended
   * in, so this names the single calendar day the figure actually covers. Null with day_change.
   */
  day_change_as_of?: string | null;
  /** CAMS "Wt.Avg.Days" — capital-weighted average holding period in days; null when no active cost remains */
  wt_avg_days?: number | null;
  /**
   * ADR-0039 — % of total_value that wt_avg_days' ledger-only basis covers (mirrors
   * xirr_coverage_pct's math). null when wt_avg_days is itself null, or coverage is full.
   */
  wt_avg_days_coverage_pct?: number | null;
  /**
   * ADR-0039 — % of total_value that day_change's covered holdings (2 recent NAV dates, at the
   * anchor) represent. null when day_change is itself null, or coverage is full.
   */
  day_change_coverage_pct?: number | null;
  fund_count: number;
  funds_scored: number;
  /** Data-confidence band for the portfolio as a whole — a data-quality descriptor, NOT a verdict */
  confidence_band: 'high' | 'medium' | 'low' | null;
  as_of: string | null;
  /**
   * ADR-0039 — the NAV pricing anchor date (day-change's anchor date, else the latest on-file NAV
   * date across holdings) — distinct from `as_of` (the statement date); never conflated with it.
   */
  valuation_as_of?: string | null;
  /** Owner's own CAS-captured name (their own name to their own session, DPDP-fine) — null until
   * a CAS upload has captured it. Their PAN is never included in this payload. */
  investor_name?: string | null;
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

// ---------------------------------------------------------------------------
// Transactions types (DataEnvelope) — P1, the append-only ledger, owner-scoped.
// ---------------------------------------------------------------------------

/** Canonical transaction type (mf/cas.py::_CANON_TXN_TYPE) — not an advisory verb. */
export type TransactionType =
  | 'purchase'
  | 'sip'
  | 'redemption'
  | 'switch_in'
  | 'switch_out'
  | 'dividend_payout'
  | 'dividend_reinvest';

export interface Transaction {
  id: string;
  isin: string;
  folio_number: string;
  txn_type: TransactionType | string;
  txn_date: string;
  /** User's own units for this row — allowed in DOM */
  units: number;
  nav_or_price: number | null;
  /** B65-signed: outflow negative, inflow positive — allowed in DOM (§13) */
  amount: number;
}

export interface TransactionsPayload {
  portfolio_id: string;
  isin: string | null;
  count: number;
  total: number;
  limit: number;
  offset: number;
  transactions: Transaction[];
}

/** P1 `holding.transactions` — GET /api/v1/portfolio/{id}/transactions?isin=&limit=.
 * No cache (personal, ledger-fresh) — matches the backend's no-cache contract. */
export function usePortfolioTransactions(
  portfolioId: string,
  opts?: { isin?: string; limit?: number },
) {
  const isin = opts?.isin;
  const limit = opts?.limit ?? 50;
  return useQuery<DataEnvelope<TransactionsPayload>>({
    queryKey: queryKeys.portfolio.transactions(portfolioId, isin),
    queryFn: () => {
      const qs = new URLSearchParams({ limit: String(limit) });
      if (isin) qs.set('isin', isin);
      return api.get<DataEnvelope<TransactionsPayload>>(
        `/portfolio/${portfolioId}/transactions?${qs.toString()}`,
      );
    },
    enabled: !!portfolioId,
    retry: (count, error) => {
      if (error instanceof ApiError && SKIP_RETRY.includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 0,
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
 * M2.3 (resolves B88): `risk_band_basis` names which series volatility_pct/max_drawdown_pct/
 * recovery_months actually come from — "portfolio return series" (true, real numbers) once the
 * portfolio's own daily valuation series is long enough, else "average fund volatility" (the
 * original fallback, with max_drawdown_pct/recovery_months honestly null → "coming soon").
 */
export interface RiskPayload {
  portfolio_id: string;
  /** Risk band — factual descriptor; basis (true series or indicative fallback) is in risk_band_basis */
  risk_band: 'low' | 'moderate' | 'high' | 'very_high' | null;
  /** Which series risk_band/volatility_pct/max_drawdown_pct are based on (M2.3) */
  risk_band_basis: string | null;
  /** Annualised volatility — the TRUE portfolio σ once the series is long enough, else the avg fund proxy */
  volatility_pct: number | null;
  /** Peak-to-trough decline % — real once the series is long enough, else null ("coming soon") */
  max_drawdown_pct: number | null;
  /** Months to recover from the biggest fall — real once the series is long enough, else null */
  recovery_months: number | null;
  fund_count: number;
  funds_with_metrics: number;
  as_of: string | null;
}

/**
 * Advanced risk payload returned by GET /portfolio/{id}/risk?advanced=true.
 * Requires Plus tier; free users get HTTP 402.
 * M2.3 (resolves B88): sharpe_ratio/sortino_ratio/rolling_1y_pct_positive are real once the
 * portfolio's own daily valuation series is long enough (see RiskPayload.risk_band_basis on the
 * sibling free endpoint); otherwise null. `alpha`/`beta` are always null server-side (not built yet).
 */
export interface RiskAdvancedPayload {
  portfolio_id: string;
  /** Standard Sharpe ratio — DOM-allowed; real once the series is long enough (M2.3) */
  sharpe_ratio: number | null;
  /** Standard Sortino ratio — DOM-allowed; real once the series is long enough (M2.3) */
  sortino_ratio: number | null;
  /** Rolling 1-year average return % — DOM-allowed */
  rolling_1y_avg_pct: number | null;
  /** % of rolling 1Y windows that were positive — real once the series is long enough (M2.3) */
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
  /**
   * Flow-neutral time-weighted-return wealth index (PR-C), base 100.0 at the FIRST point of this
   * series. A deposit/redemption never moves it — rebase any window client-side purely by
   * division: `(twr_index_t / twr_index_window_start - 1) * 100`. This is the series Section 2's
   * "You" return line and the hero P&L% are built from — never `value`, which a large deposit
   * inflates (the founder-reported +212% fake-gain bug).
   */
  twr_index: number;
}

export interface ValueSeriesPayload {
  portfolio_id: string;
  point_count: number;
  /**
   * The portfolio's earliest ledger transaction date (ISO date string), falling back to the first
   * `points` row when the ledger has no rows yet. Anchors the "All" window and the adaptive
   * period-pill ladder (age = today - first_investment_date). Null only on a genuine cold start.
   */
  first_investment_date: string | null;
  /** All available daily data points, ordered ascending by date. Empty on cold-start. */
  points: ValueSeriesPoint[];
}

/**
 * Hook for the full daily portfolio-value series (all available rows, no period cap).
 * Returns an empty `points` array on cold-start (M2.2 data starts 2026-07-01, forward-only).
 * The front-end windows the data for the chart/sparkline — no `days` param needed.
 */
/**
 * Calls the existing M2.2 /valuation-series endpoint with ?days=3650 (the full
 * available ~10-year window). The FE windows locally for the chart/sparkline.
 */
export function usePortfolioValueSeries(portfolioId: string) {
  return useQuery<DataEnvelope<ValueSeriesPayload>>({
    queryKey: queryKeys.portfolio.valueSeries(portfolioId),
    queryFn: () =>
      api.get<DataEnvelope<ValueSeriesPayload>>(`/portfolio/${portfolioId}/valuation-series?days=3650`),
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
 * Any registered benchmark's price-index daily close series from
 * GET /mf/benchmark/{key} (item 3, 2026-07 — category-benchmark overlays).
 * Public endpoint — no auth needed. Optional from/to ISO date filters.
 * `enabled: false` skips the fetch (used for the nifty50 empty-series fallback
 * on the fund detail Returns tab, so it only fires when actually needed).
 */
export function useBenchmarkSeries(
  benchmark: string,
  params?: { from?: string; to?: string },
  options?: { enabled?: boolean },
) {
  const searchParams = new URLSearchParams();
  if (params?.from) searchParams.set('from', params.from);
  if (params?.to) searchParams.set('to', params.to);
  const qs = searchParams.toString();
  return useQuery<NiftyCloseSeriesPayload>({
    queryKey: queryKeys.benchmark.byKey(benchmark, params),
    queryFn: () =>
      api.get<NiftyCloseSeriesPayload>(`/mf/benchmark/${benchmark}${qs ? `?${qs}` : ''}`),
    enabled: options?.enabled ?? true,
    retry: (count, error) => {
      if (error instanceof ApiError && SKIP_RETRY.includes(error.problem.status)) return false;
      return count < 1;
    },
    staleTime: 10 * 60 * 1000, // closes change only once a day
  });
}

/**
 * Nifty 50 price-index daily close series from GET /mf/benchmark/nifty50.
 * Thin nifty50-only wrapper around `useBenchmarkSeries` — kept so the
 * Portfolio-vs-Market chart (always nifty50) doesn't need to know about the
 * benchmark registry.
 */
export function useNiftyCloseSeries(params?: { from?: string; to?: string }) {
  return useBenchmarkSeries('nifty50', params);
}

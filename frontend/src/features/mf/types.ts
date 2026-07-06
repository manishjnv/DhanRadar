import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';
import type { DataEnvelope } from '@/data/envelope';

export interface CasUploadResponse {
  job_id: string;
  estimated_seconds: number;
}

// ---------------------------------------------------------------------------
// Backend wire shapes (source of truth = deployed FastAPI; DO NOT change backend)
// ---------------------------------------------------------------------------

/** Status values the backend actually emits on GET /api/v1/mf/upload/cas/{job_id}/status */
export type BackendCasStatus = 'queued' | 'parsing' | 'scoring' | 'done' | 'failed';

export interface BackendCasJobStatus {
  job_id: string;
  status: BackendCasStatus;
  progress_pct: number;
  error_message: string | null;
}

export interface BackendFund {
  isin: string;
  scheme_name: string;
  folio_number: string;
  /** AMFI category from the mf_funds master; null when the ISIN isn't in the master. */
  category?: string | null;
  units: number;
  /** null when CAS has no cost basis (CDSL / no-transaction holdings) */
  invested_amount: number | null;
  current_value: number;
  verb_label: string;
  confidence_band: string;
  contributing_signals: string[];
  contradicting_signals: string[];
  /** Feature 3: label from previous upload; null on first-ever upload. */
  previous_label: string | null;
  /** Feature 4: named confidence quality signals — string bands only. null on old cached reports. */
  confidence_factors?: Record<string, 'high' | 'medium' | 'low'> | null;
  /** Feature 5: market-wide ordinal rank within sebi_category peer group.
   *  null/absent before the nightly compute_market_ranks has run or when fund has no sebi_category. */
  category_rank?: number | null;
  category_total?: number | null;
}

/** Wire shape returned by GET /api/v1/mf/report/{job_id} */
export interface BackendPortfolioReport {
  job_id: string;
  status: 'done';
  total_invested: number;
  current_value: number;
  xirr_pct: number;
  category_allocation: Record<string, number>;
  overlap_matrix: Record<string, Record<string, number>>;
  funds: BackendFund[];
  /** Backend returns a dict: {state:"ok",commentary:"...",...} or {state:"unavailable",...} or null */
  commentary: { state: string; commentary?: string } | null;
  model_version: string | null;
  generated_at: string | null;
  /** Feature 2/3: forwarded from MfCasJob.portfolio_id for the history endpoint. */
  portfolio_id: string | null;
  disclosure: string;
  not_advice: string;
  disclaimer_version: string | null;
}

export interface CasStatusResponse {
  status: 'pending' | 'processing' | 'done' | 'error';
  progress_pct: number;
}

export interface MfScheme {
  isin: string;
  scheme_name: string;
  amc_name: string;
  category: string;
  units: number;
  /** User's own money figures — allowed in DOM per architecture rule.
   *  null when CAS has no cost basis (CDSL / no-transaction holdings). */
  invested: number | null;
  current_value: number;
  return_pct: number;
  /** Non-advisory label (never advisory verbs) */
  label: Label;
  confidence_band: ConfidenceBand;
  /** Educational "why this label" signals — verbatim from the scoring engine's
   *  compliance-approved vocabulary (backend `contributing_signals` /
   *  `contradicting_signals`). Rendered by <WhyThisLabelPanel/>. The backend
   *  already sends these on every fund; they MUST be forwarded, not dropped. */
  contributing_signals: string[];
  contradicting_signals: string[];
  /** Feature 3: label from the previous CAS upload for the delta (↑/↓) indicator.
   *  null on first-ever upload or when prior history is unavailable. */
  previous_label: Label | null;
  /** Feature 4: named confidence quality signals — "high"/"medium"/"low" only, never floats.
   *  null/absent on old cached reports; UI degrades gracefully when missing. */
  confidence_factors?: Record<string, 'high' | 'medium' | 'low'> | null;
  /** Feature 5: market-wide ordinal rank within sebi_category peer group.
   *  null when not yet computed or fund has no sebi_category. */
  category_rank?: number | null;
  category_total?: number | null;
}

export interface AllocationSlice {
  category: string;
  pct: number;
}

export interface OverlapPair {
  fund_a: string;
  fund_b: string;
  overlap_pct: number;
}

export interface MfReportSummary {
  /** User's own money figures — allowed in DOM */
  total_invested: number;
  current_value: number;
  xirr_pct: number;
  as_of: string;
  scheme_count: number;
}

export interface LabelHistoryEntry {
  isin: string;
  snapshot_date: string;
  verb_label: Label;
  confidence_band: ConfidenceBand;
}

// ---------------------------------------------------------------------------
// F2 — Research assistant /ask endpoint response
// ---------------------------------------------------------------------------

/** Wire shape returned by POST /api/v1/mf/report/{job_id}/ask */
export interface ResearchAskResponse {
  state: 'ok' | 'insufficient_data' | 'unavailable' | 'daily_cap';
  answer?: string;
  citations?: string[];
  refusal_triggered?: boolean;
  confidence_band?: string;
  contributing_signals?: string[];
  contradicting_signals?: string[];
  disclaimer?: string;
  disclaimer_version?: string;
  /** Machine reason code on non-ok states: consent_required, cap_unavailable, etc. */
  reason?: string;
}

/** Returned by GET /api/v1/mf/portfolio/latest — enables "view portfolio without
 *  re-uploading" flow. The frontend uses job_id to navigate to the report page. */
export interface PortfolioLatestResponse {
  job_id: string;
  portfolio_id: string;
  portfolio_name: string;
}

// ---------------------------------------------------------------------------
// Feature 6 — Fund Explorer (public, no user data)
// ---------------------------------------------------------------------------

/** One fund row returned by GET /api/v1/mf/funds */
export interface FundExplorerItem {
  isin: string;
  scheme_name: string;
  /** Display-only clean name (server-derived); null on old cached rows. */
  fund_name_short: string | null;
  amc_name: string | null;
  sebi_category: string;
  verb_label: Label;
  /** null until mf_fund_ranks stores confidence_band (future enhancement) */
  confidence_band: ConfidenceBand | null;
  /** null — stored when compute_market_ranks is extended */
  confidence_factors: Record<string, 'high' | 'medium' | 'low'> | null;
  category_rank: number;
  category_total: number;
  return_3m_pct: number | null;
  return_6m_pct: number | null;
  return_1y_pct: number | null;
  return_3y_pct: number | null;
  return_5y_pct: number | null;
  /** B67 Task 3: parsed from scheme name — null for legacy schemes */
  plan_type: 'direct' | 'regular' | null;
  /** B67 Task 3: parsed from scheme name — null for legacy schemes */
  option_type: 'growth' | 'idcw' | 'dividend_reinvest' | 'dividend_payout' | null;
  /** IDCW payout cadence parsed from scheme name — null for non-IDCW/legacy. */
  idcw_frequency: 'daily' | 'weekly' | 'fortnightly' | 'monthly' | 'quarterly' | 'half_yearly' | 'annual' | null;
  /** ADR-0035: AMC-level AUM — null until AMFI SPA endpoint confirmed */
  amc_level_aum_crore: number | null;
}

/** Response shape for GET /api/v1/mf/funds */
export interface FundExplorerResponse {
  funds: FundExplorerItem[];
  total: number;
  page: number;
  limit: number;
  disclosure: string;
  not_advice: string;
}

// ---------------------------------------------------------------------------
// W0 — fund.head (single-ISIN public read model, GET /api/v1/mf/fund/{isin})
// FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §7/§8. Wire shape of the envelope's
// `data` field — replaces the 30-page explorer-scan pagination hack.
// ---------------------------------------------------------------------------
export interface FundHead {
  isin: string;
  scheme_name: string;
  fund_name_short: string | null;
  amc_name: string | null;
  sebi_category: string | null;
  category: string | null;
  plan_type: 'direct' | 'regular' | null;
  option_type: 'growth' | 'idcw' | 'dividend_reinvest' | 'dividend_payout' | null;
  idcw_frequency: 'daily' | 'weekly' | 'fortnightly' | 'monthly' | 'quarterly' | 'half_yearly' | 'annual' | null;
  launch_date: string | null;
  expense_ratio_pct: number | null;
  is_segregated: boolean;
  verb_label: Label | null;
  category_rank: number | null;
  category_total: number | null;
  rank_as_of: string | null;
  return_3m_pct: number | null;
  return_6m_pct: number | null;
  return_1y_pct: number | null;
  return_3y_pct: number | null;
  return_5y_pct: number | null;
  metrics_as_of: string | null;
  nav_latest: number | null;
  nav_date: string | null;
  nav_change_pct: number | null;
  /** W2 (§10.1): real once the fund is ranked; null when unranked or insufficient_data. */
  confidence_band: ConfidenceBand | null;
  /** W3 field — source-blocked (B67/ADR-0035), always null today. */
  amc_level_aum_crore: number | null;
  /** Per-scheme AUM from the SEBI monthly portfolio disclosure's grand-total row
   * (never AMC-level; ADR-0035). Null until that scheme's file has been ingested. */
  aum_crore: number | null;
  /** Disclosure file's own as_of_month for aum_crore — never the ingestion run time. */
  aum_as_of: string | null;
}

// ---------------------------------------------------------------------------
// W1 — fund.nav_series, fund.analytics, fund.rank_history, fund.composition,
// fund.people, fund.amc, fund.peers (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §7/§8/§17 W1).
// Wire shapes of each envelope's `data` field.
// ---------------------------------------------------------------------------

/** GET /api/v1/mf/fund/{isin}/nav?range=... */
export interface FundNavPoint {
  /** ISO date (YYYY-MM-DD) */
  d: string;
  nav: number;
}
export interface FundNavSeries {
  range: '1m' | '3m' | '6m' | '1y' | '3y' | '5y' | 'max';
  points: FundNavPoint[];
  from: string | null;
  to: string | null;
  n_total: number;
}

/** Category percentile band for one metric (p25/p50/p75/p90), from GET .../analytics */
export interface CategoryPercentileBand {
  p25: number | null;
  p50: number | null;
  p75: number | null;
  p90: number | null;
}

/** One point of the `drawdown_series` (§10.5) — pct is always <= 0. */
export interface FundDrawdownPoint {
  d: string;
  pct: number;
}

/** One calendar-year entry of `calendar_year_returns` (§10.5). quartile is null
 *  when the category hasn't published enough funds for that year yet. */
export interface FundCalendarYearReturn {
  year: number;
  return_pct: number;
  quartile: 1 | 2 | 3 | 4 | null;
}

export interface FundAnalytics {
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  volatility_pct: number | null;
  max_drawdown_pct: number | null;
  rolling_1y_avg_pct: number | null;
  rolling_1y_min_pct: number | null;
  rolling_1y_max_pct: number | null;
  rolling_1y_pct_positive: number | null;
  /** W2 §10.5 — same shape as the rolling_1y_* fields, 3-year window. */
  rolling_3y_avg_pct: number | null;
  rolling_3y_min_pct: number | null;
  rolling_3y_max_pct: number | null;
  rolling_3y_pct_positive: number | null;
  /** Block 0.7 — CAPM alpha/beta/tracking error vs the fund's mapped
   *  benchmark_index. Populated ONLY for index funds with a high-confidence
   *  benchmark mapping (mf/benchmark_mapping.py); null for every other fund. */
  alpha_1y: number | null;
  beta_1y: number | null;
  tracking_error_pct: number | null;
  as_of: string | null;
  /** 0-100; higher = more volatile than category peers. null if uncategorised/uncohorted. */
  volatility_percentile: number | null;
  /** Keys present only when the category has enough funds to publish that metric. */
  category_percentiles: Partial<
    Record<'return_1y_pct' | 'return_3y_pct' | 'max_drawdown_pct', CategoryPercentileBand>
  >;
  /** W2 §10.5 — stride-sampled to <=200 points; the caller draws the chart. */
  drawdown_series: FundDrawdownPoint[];
  worst_fall_pct: number | null;
  recovery_days: number | null;
  calendar_year_returns: FundCalendarYearReturn[];
}

export interface FundRankHistoryPoint {
  as_of: string;
  rank: number;
  total: number;
}
export interface FundRankHistory {
  points: FundRankHistoryPoint[];
}

/** GET /api/v1/mf/fund/{isin}/health (§10.7) — traffic-light dimension. */
export interface FundHealthLight {
  name: string;
  light: 'g' | 'y' | 'r' | 'grey';
  note: string;
}
export interface FundHealth {
  lights: FundHealthLight[];
  as_of: string | null;
}

/** GET /api/v1/mf/fund/{isin}/analytics — three concepts, one route (W1 + W2 health). */
export interface FundAnalyticsResponse {
  analytics: DataEnvelope<FundAnalytics>;
  rank_history: DataEnvelope<FundRankHistory>;
  health: DataEnvelope<FundHealth>;
}

/** GET /api/v1/mf/fund/{isin}/sip?amount=&years= (§10.4) — historical illustration,
 *  never a projection. Money fields are null under 12 months of history. */
export interface FundSipIllustration {
  amount: number;
  years: number;
  months_invested: number;
  total_invested: number | null;
  final_value: number | null;
  xirr_pct: number | null;
  as_of: string | null;
  assumptions: string;
}

/** GET /api/v1/mf/fund/{isin}/composition */
export interface FundHolding {
  name: string;
  sector: string | null;
  weight_pct: number | null;
}
export interface FundSectorWeight {
  name: string;
  weight_pct: number;
}
/** Market-cap mix of the SAME top-holdings rows above, joined against AMFI's
 * half-yearly stock classification. Percentages are of top-holdings weight
 * actually classified — they do NOT renormalize to 100 (a fund whose top-10
 * covers 60% of AUM shows a cap_mix that sums to <=60%, not 100). */
export interface FundCapMix {
  large_pct: number | null;
  mid_pct: number | null;
  small_pct: number | null;
  unclassified_pct: number | null;
  basis: 'top_holdings_weight';
  as_of_period: string | null;
}
export interface FundComposition {
  holdings: FundHolding[];
  sectors: FundSectorWeight[];
  cap_mix: FundCapMix;
  as_of_month: string | null;
  coverage: { holdings_count: number; weight_covered_pct: number | null };
}

/** GET /api/v1/mf/fund/{isin}/flows — item 2. CATEGORY-LEVEL ONLY: every point is the
 * trailing-12-month AMFI category-flow figure for funds sharing this fund's scheme
 * category, NEVER this fund's own money flow. Any UI copy MUST say "funds in this
 * category" — never imply the specific fund's own flows (compliance §14.3). */
export interface FundFlowPoint {
  period_month: string;
  net_flow_cr: number | null;
  net_aum_cr: number | null;
}
export interface FundFlows {
  points: FundFlowPoint[];
  scheme_category: string | null;
  as_of_month: string | null;
}

/** GET /api/v1/portfolio/{portfolio_id}/fit?isin=... — item 1. Personal, auth-required.
 * OBSERVATION ONLY: overlap_pct and category_allocation_pct are independent facts,
 * never combined into a verdict. `observation` is server-generated factual copy —
 * render as-is, never paraphrase into advisory language. */
export interface FundFitOverlapEntry {
  /** The user's own held fund's display name — DOM-allowed (own portfolio fact). */
  holding_name: string;
  /** Pairwise disclosed-holdings overlap % between that held fund and the viewed fund. */
  overlap_pct: number;
}

export interface FundFit {
  portfolio_id: string;
  viewed_isin: string;
  overlap_pct: number | null;
  category_allocation_pct: number | null;
  /** How many of the user's own held funds share the viewed fund's category; null when the
   * viewed fund has no category on file (same gating as category_allocation_pct). */
  fund_count_in_category: number | null;
  /** Top 3 held funds by pairwise disclosed-holdings overlap with the viewed fund, sorted
   * desc. Empty when no held fund had usable constituent data (see overlap_coverage). */
  overlap: FundFitOverlapEntry[];
  /** Honest completeness signal: true only when at least one held fund actually had
   * disclosed-holdings data to compare against. Constituent disclosures exist for a
   * handful of top-10 AMCs today — most portfolios will read false here. */
  overlap_coverage: boolean;
  data_completeness: 'empty' | 'no_constituent_data' | 'constituent_data';
  observation: string;
}

/** GET /api/v1/mf/fund/{isin}/people */
export interface FundManager {
  name: string;
  start_date: string;
  tenure_years: number;
  /** Return from the NAV on/before start_date to the latest NAV. Present only
   * for a current manager whose start_date is covered by NAV history —
   * omitted (not zero) otherwise. Facts only, no advisory framing. */
  tenure_return_pct?: number;
  /** ISO date of the latest NAV used for tenure_return_pct. */
  tenure_return_as_of?: string;
}
export interface FundPeople {
  managers: FundManager[];
  manager_changes_5y: number;
}
export interface FundAmc {
  amc_name: string | null;
  scheme_count: number;
  category_count: number;
}
/** GET /api/v1/mf/fund/{isin}/people — two concepts, one route. */
export interface FundPeopleResponse {
  people: DataEnvelope<FundPeople>;
  amc: DataEnvelope<FundAmc>;
}

/** GET /api/v1/mf/fund/{isin}/peers */
export interface FundPeer {
  isin: string;
  scheme_name: string;
  fund_name_short: string | null;
  amc_name: string | null;
  verb_label: Label | null;
  category_rank: number;
  return_1y_pct: number | null;
  return_3y_pct: number | null;
  expense_ratio_pct: number | null;
  volatility_pct: number | null;
}
export interface FundPeers {
  peers: FundPeer[];
}

// ---------------------------------------------------------------------------
// W2 — fund.factors + fund.signals (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.1,
// §17 W2 — the second scored concept). Wire shapes of GET .../factors.
// ---------------------------------------------------------------------------

/** Named confidence-quality bands from the scoring engine (consistency/recency/
 * volatility/data_coverage today) — band words only, never a numeric (non-neg #2).
 * null when the fund is unranked or its latest read was insufficient_data. */
export interface FundFactors {
  factors: Record<string, 'high' | 'medium' | 'low'> | null;
  confidence_band: ConfidenceBand | null;
  as_of: string | null;
}

/** Plain-word reasons for/against the current label — never advisory verbs. */
export interface FundSignals {
  contributing: string[];
  contradicting: string[];
  as_of: string | null;
}

/** GET /api/v1/mf/fund/{isin}/factors — two concepts, one route. */
export interface FundFactorsResponse {
  factors: DataEnvelope<FundFactors>;
  signals: DataEnvelope<FundSignals>;
}

/** GET /api/v1/mf/fund/{isin}/events — What-Changed events (§10.6, §17 W2). */
export interface FundEvent {
  event_type: 'rank_change' | 'ter_change' | 'holding_change';
  as_of: string;
  /** One plain factual sentence, templated server-side — render verbatim. */
  summary: string;
  payload: Record<string, unknown>;
}
export interface FundEvents {
  events: FundEvent[];
}

/** One item from GET /api/v1/mf/funds/categories */
export interface FundCategory {
  key: string;           // full SEBI string, e.g. "Equity Scheme - Large Cap Fund"
  display_name: string;  // shortened, e.g. "Large Cap Fund"
  fund_count: number;
}

/** Response shape for GET /api/v1/mf/funds/categories */
export interface FundCategoriesResponse {
  categories: FundCategory[];
}

export interface MfReport {
  summary: MfReportSummary;
  schemes: MfScheme[];
  category_allocation: AllocationSlice[];
  overlap: OverlapPair[];
  /** Feature 2/3: needed to call GET /api/v1/mf/history?portfolio_id={id}. */
  portfolio_id: string | null;
  /** Plain-language AI-generated educational commentary from the governed gateway
   *  (consent-gated; null when not consented / not generated). Rendered verbatim by
   *  <PortfolioCommentaryCard/>. */
  commentary: string | null;
  /** Contextual compliance disclosure (non-negotiable #9) — rendered next to
   *  the holdings labels via <DisclosureBundle/>. */
  disclosure: string;
  not_advice: string;
}

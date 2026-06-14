import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

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

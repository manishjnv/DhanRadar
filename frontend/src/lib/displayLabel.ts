/**
 * displayLabel — centralized raw-value → human-readable display map for the
 * admin / AI-Ops surface (UX audit P0/H).
 *
 * RULE: raw backend identifiers (snake_case enums, dotted Celery task names,
 * UPPER_CASE flag keys, internal table names, AI/ML jargon) must NEVER render
 * directly to a non-technical operator. Look a value up here; unknown values
 * fall back to Title Case via `titleCase()`.
 *
 * Educational, non-advisory display only — values here are deliberately free of
 * advisory verbs (non-neg #1/#2). The churn-decision "review needed" key is
 * built non-literally so the ci_guards advisory scan does not false-positive on
 * this educational mapping.
 */

// ---------------------------------------------------------------------------
// Title-case fallback for any unmapped raw value.
// "nav_daily_fetch" → "Nav Daily Fetch"; "dhanradar.tasks.mf.x" → last segment.
// ---------------------------------------------------------------------------
export function titleCase(raw: string | null | undefined): string {
  if (raw == null || raw === '') return '—';
  let s = String(raw);
  // For dotted identifiers, use the final segment (the action name).
  if (s.includes('.')) s = s.split('.').filter(Boolean).pop() ?? s;
  return s
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Domain maps
// ---------------------------------------------------------------------------

// Celery beat task names (Operations Jobs table + run drawer).
export const TASK_LABELS: Record<string, string> = {
  'dhanradar.tasks.mf.nav_daily_fetch': 'Daily NAV Refresh',
  'dhanradar.tasks.mf.mf_metrics_refresh': 'Fund Metrics Refresh',
  'dhanradar.tasks.mf.compute_market_ranks': 'Category Rank Update',
  'dhanradar.tasks.mf.daily_portfolio_refresh': 'Portfolio Refresh',
  'dhanradar.tasks.mf.purge_cas_files': 'CAS File Cleanup',
  'dhanradar.tasks.mf.monthly_rescore_plus_users': 'Monthly Re-score (Plus)',
  'dhanradar.tasks.mf.reap_stuck_cas_jobs': 'Stuck Upload Reaper',
  'dhanradar.tasks.mf.mf_constituents_fetch': 'Fund Holdings (Top AMCs)',
  'dhanradar.tasks.mf.mf_kite_enrich': 'Instrument Enrichment',
  'dhanradar.tasks.mf.mf_scheme_master_refresh': 'AMFI Scheme Master',
  'dhanradar.tasks.mf.mf_expense_ratio_fetch': 'Expense Ratios (TER)',
  'dhanradar.tasks.mf.mf_fund_manager_fetch': 'Fund Managers',
  'dhanradar.tasks.mf.sebi_circulars_fetch': 'SEBI Circulars',
  'dhanradar.tasks.mf.macro_data_refresh': 'RBI Macro Data',
  'dhanradar.tasks.news.refresh_market_news': 'Market News Refresh',
  'dhanradar.tasks.signal_alerts.market_data_refresh': 'Market Data Update',
  'dhanradar.tasks.signal_alerts.daily_signal_alert': 'Daily Signal Alert',
  'dhanradar.tasks.signal_alerts.market_data_refresh ': 'Market Data Update',
  'dhanradar.tasks.signal_alerts.auto_log_no_action': 'Auto-Log No Action',
  'dhanradar.tasks.signal_alerts.sip_reminder': 'SIP Reminder',
  'dhanradar.tasks.signal_alerts.check_achievements': 'Achievement Check',
  'dhanradar.tasks.misc.drain_notifications': 'Notification Delivery',
  'dhanradar.tasks.compliance.archive_audit_daily': 'Audit Archive',
  'dhanradar.tasks.compliance.reconcile_audit_disclaimers': 'Disclaimer Reconcile',
  'dhanradar.tasks.mood.compute_mood_snapshot': 'Market Mood Snapshot',
};

// Subscription tier / plan.
export const TIER_LABELS: Record<string, string> = {
  free: 'Free',
  trial: 'Trial',
  trialing: 'Trial',
  plus: 'Plus',
  pro: 'Plus',
  pro_plus: 'Plus',
  founder_lifetime: 'Founder Lifetime',
};

// Payment event status (Razorpay).
export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  captured: 'Paid',
  authorized: 'Authorized',
  pending: 'Pending',
  failed: 'Failed',
  refunded: 'Refunded',
  created: 'Created',
};

// Subscription status.
export const SUB_STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  trialing: 'Trial',
  past_due: 'Overdue',
  canceled: 'Cancelled',
  cancelled: 'Cancelled',
};

// Admin audit actions (full domain of audit.admin_actions.action).
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  suspend_user: 'Suspend User',
  unsuspend_user: 'Unsuspend User',
  reset_access: 'Clear Login Lockout',
  set_user_plan: 'Change Plan',
  sync_source: 'Refresh Data Source',
  pause_source: 'Pause Data Source',
  resume_source: 'Resume Data Source',
  trigger_task: 'Run Job Now',
  pause_task: 'Pause Job',
  resume_task: 'Resume Job',
  acknowledge_quality_issue: 'Snooze Quality Alert',
  activate_disclaimer: 'Activate Disclaimer',
  refund_payment: 'Issue Refund',
  set_budget_caps: 'Update AI Budget Caps',
  activate_scoring_model: 'Activate Scoring Model',
  create_prompt_version: 'Create AI Prompt Version',
  activate_prompt_version: 'Activate AI Prompt Version',
  broadcast: 'Send Broadcast',
  set_cas_support_notes: 'Add Support Note',
  upload_disclosure_files: 'Upload Disclosure Files',
  create_news_item: 'Create News Item',
  update_news_item: 'Edit News Item',
  delete_news_item: 'Delete News Item',
};

// Admin audit target types (what an admin action was applied to).
export const TARGET_TYPE_LABELS: Record<string, string> = {
  user: 'User',
  payment: 'Payment',
  source: 'Data source',
  task: 'Background job',
  data_quality: 'Data-quality alert',
  disclaimer: 'Disclaimer',
  scoring_model: 'Scoring model',
  prompt_template: 'AI prompt',
  ai_budget: 'AI spending limit',
  cas_job: 'CAS upload',
  notification: 'Broadcast',
  manual_ingest: 'Disclosure files',
  news_item: 'News item',
};

// Data-source keys (mirrors the backend source catalog; titleCase fallback
// covers any key added on the backend before this map is updated).
export const SOURCE_LABELS: Record<string, string> = {
  amfi_nav: 'AMFI Daily NAV',
  amfi_scheme_master: 'AMFI Scheme Master',
  amc_constituents: 'AMC Portfolio Disclosures',
  amc_expense_ratios: 'AMC Expense Ratios',
  amc_fund_managers: 'AMC Fund Managers',
  sebi_circulars: 'SEBI Circulars',
  amfi_cap_classification: 'AMFI Cap Classification',
  amfi_category_flows: 'AMFI Category Flows',
  mfapi: 'MFAPI NAV History',
  yahoo_finance: 'Yahoo Finance',
  nse_india: 'NSE India',
  rbi_dbie: 'RBI Macro Data',
  rbi_tbill: 'RBI T-Bill Yields',
  rbi_rss: 'RBI News Feed',
  manual_disclosure_inbox: 'Manual Disclosure Inbox',
  upstox_analytics: 'Upstox Market Analytics',
  nifty_close_daily: 'Nifty 50 Daily Close',
};

// Ops health-alert types (Overview page alert feed).
export const ALERT_TYPE_LABELS: Record<string, string> = {
  mood_missing: 'Market Mood missing',
  mood_stale: 'Market Mood outdated',
  mood_degraded: 'Market Mood incomplete',
  ingestion_failures: 'Data refresh failures',
  sources_unhealthy: 'Data sources unhealthy',
  stuck_tasks: 'Stuck background jobs',
};

// Market-mood signal keys (Mood coverage panel).
export const SIGNAL_LABELS: Record<string, string> = {
  nifty_trend: 'Nifty trend',
  market_breadth: 'Market breadth',
  india_vix: 'India VIX',
  fii_flows: 'FII flows',
  global_indices: 'Global indices',
  dii_flows: 'DII flows',
  us_bond_10y: 'US 10-yr bond',
  oil_brent: 'Brent crude oil',
  usd_inr: 'USD-INR rate',
  put_call_ratio: 'Put-call ratio',
  news_sentiment: 'News sentiment',
};

// Market-mood regime buckets + data-quality states.
export const MOOD_LABELS: Record<string, string> = {
  extreme_fear: 'Extreme Fear',
  fear: 'Fear',
  neutral: 'Neutral',
  greed: 'Greed',
  extreme_greed: 'Extreme Greed',
  data_unavailable: 'No Data',
  insufficient_data: 'Not Enough Data',
  ok: 'Complete',
  degraded: 'Incomplete (some inputs missing)',
  unavailable: 'Unavailable',
};

// Feature flag keys.
export const FLAG_LABELS: Record<string, string> = {
  AUDIT_ARCHIVE_ENABLED: 'Audit Archive',
  COOKIE_SECURE: 'Secure Cookies (HTTPS only)',
  DPDP_CONSENT_ENFORCED: 'DPDP Consent Enforcement',
};

// Educational fund labels (display only — not signals to act).
export const EDU_LABELS: Record<string, string> = {
  in_form: 'In Form',
  on_track: 'On Track',
  off_track: 'Off Track',
  out_of_form: 'Out of Form',
  insufficient_data: 'Not Enough Data',
};

// Recommendation/output category + AI surface keys (AI audit "Category" and
// "Where Shown" columns share one vocabulary).
export const RECO_TYPE_LABELS: Record<string, string> = {
  educational_label: 'Fund Evaluation',
  mood_regime: 'Market Mood',
  portfolio_commentary: 'Portfolio Commentary',
  mf_report: 'Fund Report',
  mf_research: 'Fund Research',
  mf_commentary: 'Fund Commentary',
  mood_commentary: 'Market Mood Commentary',
  notification_telegram: 'Telegram Alert',
  mf_pick: 'Fund Spotlight',
  stock_pick: 'Stock Spotlight',
  earnings_summary: 'Earnings Summary',
};

// Confidence band.
export const CONFIDENCE_BAND_LABELS: Record<string, string> = {
  high: 'High Certainty',
  medium: 'Medium Certainty',
  low: 'Low Certainty',
  insufficient_data: 'Not Enough Data',
};

// Ingestion run / job status.
export const RUN_STATUS_LABELS: Record<string, string> = {
  running: 'Running',
  success: 'Success',
  partial: 'Partial',
  failed: 'Failed',
  skipped: 'Skipped',
};

// Churn-decision (Label Churn / Answer Consistency). The held state's raw
// governance enum VALUE is "pending_publish" (BatchDecision.hold = "pending_publish"),
// NOT the literal "hold" — keying on "hold" never matched (label_churn_review returns
// decision.value). "pending_publish" carries no advisory term so it is safe to write
// literally (unlike "hold", which the ci_guards advisory scan would flag).
export const DECISION_LABELS: Record<string, string> = {
  publish: 'Stable',
  insufficient_data: 'Not Enough Data',
  pending_publish: 'Review Needed',
};

// AI / internal terms occasionally surfaced.
export const AI_TERM_LABELS: Record<string, string> = {
  ai_recommendation_audit: 'AI Output Log',
  ranking_configs: 'Score Configuration',
  registry: 'Score History',
  groundedness: 'AI Output Accuracy',
  label_churn: 'Answer Consistency',
  served_output: 'AI Responses Delivered',
  low_confidence: 'Responses Refused',
};

const DOMAINS: Record<string, Record<string, string>> = {
  task: TASK_LABELS,
  tier: TIER_LABELS,
  payment: PAYMENT_STATUS_LABELS,
  subscription: SUB_STATUS_LABELS,
  audit: AUDIT_ACTION_LABELS,
  targetType: TARGET_TYPE_LABELS,
  source: SOURCE_LABELS,
  alertType: ALERT_TYPE_LABELS,
  signal: SIGNAL_LABELS,
  mood: MOOD_LABELS,
  flag: FLAG_LABELS,
  label: EDU_LABELS,
  recoType: RECO_TYPE_LABELS,
  surface: RECO_TYPE_LABELS,
  band: CONFIDENCE_BAND_LABELS,
  runStatus: RUN_STATUS_LABELS,
  decision: DECISION_LABELS,
  aiTerm: AI_TERM_LABELS,
};

export type LabelDomain = keyof typeof DOMAINS;

/**
 * Resolve a raw backend value to human display text.
 * @param raw    the raw value (enum / task name / flag key / id)
 * @param domain optional hint to use a specific map; if omitted, all maps are
 *               searched, then a Title-Case fallback is applied.
 */
export function displayLabel(
  raw: string | null | undefined,
  domain?: LabelDomain,
): string {
  if (raw == null || raw === '') return '—';
  const key = String(raw);
  if (domain && DOMAINS[domain]?.[key] != null) return DOMAINS[domain][key];
  if (!domain) {
    for (const map of Object.values(DOMAINS)) {
      if (map[key] != null) return map[key];
    }
  }
  return titleCase(key);
}

/**
 * Humanize an AI model slug ("deepseek/deepseek-chat" → "Deepseek Chat"):
 * drop the provider prefix, title-case the model segment. The raw slug should
 * stay available in a tooltip wherever this is used.
 */
export function modelLabel(raw: string | null | undefined): string {
  if (raw == null || raw === '') return '—';
  const key = String(raw);
  const segment = key.includes('/') ? key.split('/').pop()! : key;
  return titleCase(segment.replace(/:/g, ' '));
}

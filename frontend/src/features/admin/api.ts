/**
 * Admin feature — TanStack Query hooks + mutation wrappers.
 *
 * All calls go through apiClient (cookie auth, /api/v1 base, RFC7807 errors).
 * No advisory verbs, no SEBI label system — admin shows raw operational numbers.
 * Numeric values ARE allowed in admin DOM (Admin.md §16).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------
export const adminKeys = {
  all:        () => ['admin'] as const,
  health:     () => ['admin', 'health'] as const,
  alerts:     () => ['admin', 'alerts'] as const,
  sources:    () => ['admin', 'sources'] as const,
  tasks:      () => ['admin', 'tasks'] as const,
  runs:       (params?: Record<string, unknown>) => ['admin', 'runs', params] as const,
  run:        (id: string) => ['admin', 'run', id] as const,
  quality:    () => ['admin', 'quality'] as const,
  moodStatus: () => ['admin', 'mood-status'] as const,
} as const;

// ---------------------------------------------------------------------------
// Types — mirrors the backend contract exactly (Admin.md §7)
// ---------------------------------------------------------------------------

export interface AdminHealthResponse {
  sources_healthy: number;
  sources_total: number;
  last_nav_sync: string | null;
  total_schemes: number;
  active_users: number;
  premium_users: number;
  advice_boundary_breaches_today: number;
  low_groundedness_flags_7d: number;
  recent_failures: Array<{ source: string; reason: string; failed_at: string }>;
  recent_signups: Array<{ display_name: string; plan: string; joined_at: string }>;
  recent_alerts: Array<{ type: string; message: string; severity: 'info' | 'warning' | 'critical'; created_at: string }>;
}

export interface AdminSource {
  source_key: string;
  name: string;
  tier: string;
  description: string;
  method: string;
  schedule_display: string;
  cost: string;
  last_success_at: string | null;
  last_records: number | null;
  status: string;
  paused: boolean;
}

export interface AdminTask {
  task_name: string;
  schedule_display: string;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: string | null;
  last_duration_s: number | null;
  last_rows: number | null;
  paused: boolean;
}

export interface AdminRun {
  run_id: number;
  source: string;
  task_name: string;
  started_at: string;
  finished_at: string | null;
  duration_s: number | null;
  records_written: number | null;
  records_failed: number | null;
  status: string;
  error_class: string | null;
}

export interface AdminRunDetail extends AdminRun {
  error_detail: string | null;
  raw_file_path: string | null;
  run_metadata: Record<string, unknown> | null;
}

export interface AdminQualityIssue {
  metric_key: string;
  label: string;
  current_value: number | null;
  threshold: number | null;
  unit: string;
  status: 'ok' | 'warning' | 'critical';
  acknowledged_until: string | null;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useAdminHealth() {
  return useQuery({
    queryKey: adminKeys.health(),
    queryFn: () => api.get<AdminHealthResponse>('/admin/health'),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

// Derived attention alerts for the admin bell. Only enabled for admins so a
// non-admin never fires the (404-on-non-admin) request.
export interface AdminAlert {
  key: string;
  severity: 'critical' | 'warning' | 'info';
  title: string;
  detail: string;
  since: string | null;
  href: string | null;
}
export interface AdminAlertsResponse {
  count: number;
  alerts: AdminAlert[];
}

export function useAdminAlerts(enabled: boolean) {
  return useQuery({
    queryKey: adminKeys.alerts(),
    queryFn: () => api.get<AdminAlertsResponse>('/admin/alerts'),
    enabled,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminSources() {
  return useQuery({
    queryKey: adminKeys.sources(),
    queryFn: () => api.get<AdminSource[]>('/admin/sources'),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminTasks() {
  return useQuery({
    queryKey: adminKeys.tasks(),
    queryFn: () => api.get<AdminTask[]>('/admin/tasks'),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminRuns(params?: { source?: string; status?: string; limit?: number; offset?: number }) {
  const qs = new URLSearchParams();
  if (params?.source) qs.set('source', params.source);
  if (params?.status) qs.set('status', params.status);
  if (params?.limit)  qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  const path = `/admin/runs${qs.toString() ? '?' + qs.toString() : ''}`;
  return useQuery({
    queryKey: adminKeys.runs(params),
    queryFn: () => api.get<AdminRun[]>(path),
    staleTime: 15 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminRunDetail(runId: string) {
  return useQuery({
    queryKey: adminKeys.run(runId),
    queryFn: () => api.get<AdminRunDetail>(`/admin/runs/${runId}`),
    enabled: !!runId,
    staleTime: 60 * 1000,
  });
}

export function useAdminQuality() {
  return useQuery({
    queryKey: adminKeys.quality(),
    queryFn: () => api.get<AdminQualityIssue[]>('/admin/quality'),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Market Mood signal coverage (admin-only)
// ---------------------------------------------------------------------------

export interface AdminMoodStatus {
  snapshot_at:         string | null;
  regime:              string | null;
  inputs_available:    number;
  total_signals:       number;
  data_quality:        string | null;
  signals_present:     string[];
  upstox_fii_flows:    boolean;
  upstox_dii_flows:    boolean;
  upstox_put_call_ratio: boolean;
}

export function useAdminMoodStatus() {
  return useQuery({
    queryKey: adminKeys.moodStatus(),
    queryFn: () => api.get<AdminMoodStatus>('/admin/mood-status'),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useSourceSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceKey: string) =>
      api.post<{ task_id: string }>(`/admin/sources/${sourceKey}/sync`),
    onSettled: () => qc.invalidateQueries({ queryKey: adminKeys.sources() }),
  });
}

export function useSourcePause() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceKey: string) =>
      api.post<{ ok: boolean }>(`/admin/sources/${sourceKey}/pause`),
    onSettled: () => qc.invalidateQueries({ queryKey: adminKeys.sources() }),
  });
}

export function useSourceResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceKey: string) =>
      api.post<{ ok: boolean }>(`/admin/sources/${sourceKey}/resume`),
    onSettled: () => qc.invalidateQueries({ queryKey: adminKeys.sources() }),
  });
}

export function useTaskTrigger() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskName: string) =>
      api.post<{ task_id: string }>(`/admin/tasks/${taskName}/trigger`),
    onSettled: () => qc.invalidateQueries({ queryKey: adminKeys.tasks() }),
  });
}

export function useTaskPause() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskName: string) =>
      api.post<{ ok: boolean }>(`/admin/tasks/${taskName}/pause`),
    onSettled: () => qc.invalidateQueries({ queryKey: adminKeys.tasks() }),
  });
}

export function useTaskResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskName: string) =>
      api.post<{ ok: boolean }>(`/admin/tasks/${taskName}/resume`),
    onSettled: () => qc.invalidateQueries({ queryKey: adminKeys.tasks() }),
  });
}

export function useQualityAcknowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ metricKey, durationDays }: { metricKey: string; durationDays: number }) =>
      api.post<{ ok: boolean }>(`/admin/quality/${metricKey}/acknowledge`, { duration_days: durationDays }),
    onSettled: () => qc.invalidateQueries({ queryKey: adminKeys.quality() }),
  });
}

// ---------------------------------------------------------------------------
// Users & Billing — extended query keys
// ---------------------------------------------------------------------------
export const adminKeysExt = {
  userSummary:           () => ['admin', 'users', 'summary'] as const,
  users:   (params?: Record<string, unknown>) => ['admin', 'users', 'list', params] as const,
  user:    (id: string)  => ['admin', 'users', 'detail', id] as const,
  usersActivity: (limit: number) => ['admin', 'users', 'activity', limit] as const,
  billingOverview:       () => ['admin', 'billing', 'overview'] as const,
  billingSubscriptions:  (params?: Record<string, unknown>) => ['admin', 'billing', 'subscriptions', params] as const,
  billingPayments:       (params?: Record<string, unknown>) => ['admin', 'billing', 'payments', params] as const,
  billingSubMetrics:     () => ['admin', 'billing', 'sub-metrics'] as const,
  billingWebhookHealth:  () => ['admin', 'billing', 'webhook-health'] as const,
  audit:  (params?: Record<string, unknown>) => ['admin', 'audit', params] as const,
} as const;

// ---------------------------------------------------------------------------
// Types — Users
// ---------------------------------------------------------------------------

export interface AdminUserSummary {
  total: number;
  active: number;
  premium: number;
  trials: number;
  blocked: number;
}

export interface AdminUserRow {
  id: string;
  email: string;
  display_name: string;
  tier: string;
  status: string;
  last_login_at: string | null;
  created_at: string;
}

export interface AdminUsersListResponse {
  total: number;
  users: AdminUserRow[];
}

export interface AdminUserPayment {
  user_id: string;
  razorpay_payment_id: string | null;
  status: string;
  ts: string;
  request_id: string | null;
}

export interface LoginEvent {
  event_type: string;
  method: string | null;
  occurred_at: string;
  request_id: string | null;
}

export interface AdminActivityEvent {
  user_id: string;
  email: string;
  event_type: string;
  method: string | null;
  occurred_at: string;
}

export interface AdminUserDetail {
  id: string;
  email: string;
  display_name: string;
  tier: string;
  status: string;
  created_at: string;
  last_login_at: string | null;
  pro_access_until: string | null;
  pro_access_reason: string | null;
  risk_profile: string | null;
  dpdp_consent_version: string | null;
  subscription: {
    plan: string;
    status: string;
    current_period_end: string | null;
  } | null;
  payments: AdminUserPayment[];
  login_history: LoginEvent[];
  cas_uploads: unknown[];
}

// ---------------------------------------------------------------------------
// Types — Billing
// ---------------------------------------------------------------------------

export interface AdminBillingOverview {
  mrr_inr: number;
  arpu_inr: number;
  active_subscriptions: number;
  past_due: number;
  trials: number;
}

export interface AdminSubscriptionRow {
  user_id: string;
  email: string;
  plan: string;
  status: string;
  current_period_end: string | null;
  price_inr: number;
}

export interface AdminPaymentRow {
  user_id: string;
  razorpay_payment_id: string | null;
  status: string;
  ts: string;
  request_id: string | null;
}

export interface AdminBillingSubMetrics {
  premium_count: number;
  trials: number;
  renewals_30d: number;
  churn_30d: number;
}

export interface AdminBillingWebhookHealth {
  recent_count: number;
  success_count: number;
  failed_count: number;
  last_event_at: string | null;
  /** Optional note from the backend explaining the data source (e.g. derived from payment events). */
  note?: string;
}

// ---------------------------------------------------------------------------
// Types — Audit
// ---------------------------------------------------------------------------

export interface AdminAuditRow {
  id: string;
  ts: string;
  admin_id: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  result: string;
  request_id: string | null;
}

// ---------------------------------------------------------------------------
// User hooks
// ---------------------------------------------------------------------------

export function useAdminUserSummary() {
  return useQuery({
    queryKey: adminKeysExt.userSummary(),
    queryFn: () => api.get<AdminUserSummary>('/admin/users/summary'),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminUsers(params?: { plan?: string; status?: string; search?: string; limit?: number; offset?: number }) {
  const qs = new URLSearchParams();
  if (params?.plan)   qs.set('plan',   params.plan);
  if (params?.status) qs.set('status', params.status);
  if (params?.search) qs.set('search', params.search);
  if (params?.limit)  qs.set('limit',  String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  const path = `/admin/users${qs.toString() ? '?' + qs.toString() : ''}`;
  return useQuery({
    queryKey: adminKeysExt.users(params),
    queryFn: () => api.get<AdminUsersListResponse>(path),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminUserDetail(userId: string) {
  return useQuery({
    queryKey: adminKeysExt.user(userId),
    queryFn: () => api.get<AdminUserDetail>(`/admin/users/${userId}`),
    enabled: !!userId,
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminUserActivity(limit = 50) {
  return useQuery({
    queryKey: adminKeysExt.usersActivity(limit),
    queryFn: () => api.get<AdminActivityEvent[]>(`/admin/users/activity?limit=${limit}`),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Billing hooks
// ---------------------------------------------------------------------------

export function useAdminBillingOverview() {
  return useQuery({
    queryKey: adminKeysExt.billingOverview(),
    queryFn: () => api.get<AdminBillingOverview>('/admin/billing/overview'),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminSubscriptions(params?: { status?: string; limit?: number; offset?: number }) {
  const qs = new URLSearchParams();
  if (params?.status) qs.set('status', params.status);
  if (params?.limit)  qs.set('limit',  String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  const path = `/admin/billing/subscriptions${qs.toString() ? '?' + qs.toString() : ''}`;
  return useQuery({
    queryKey: adminKeysExt.billingSubscriptions(params),
    queryFn: () => api.get<AdminSubscriptionRow[]>(path),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminBillingPayments(params?: { limit?: number; offset?: number }) {
  const qs = new URLSearchParams();
  if (params?.limit)  qs.set('limit',  String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  const path = `/admin/billing/payments${qs.toString() ? '?' + qs.toString() : ''}`;
  return useQuery({
    queryKey: adminKeysExt.billingPayments(params),
    queryFn: () => api.get<AdminPaymentRow[]>(path),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminBillingSubMetrics() {
  return useQuery({
    queryKey: adminKeysExt.billingSubMetrics(),
    queryFn: () => api.get<AdminBillingSubMetrics>('/admin/billing/subscription-metrics'),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminBillingWebhookHealth() {
  return useQuery({
    queryKey: adminKeysExt.billingWebhookHealth(),
    queryFn: () => api.get<AdminBillingWebhookHealth>('/admin/billing/webhook-health'),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Phase 3 extended query keys
// ---------------------------------------------------------------------------
export const adminKeysP3 = {
  scoringModel:          () => ['admin', 'scoring', 'model'] as const,
  flags:                 () => ['admin', 'flags'] as const,
  supportCasFailures:    () => ['admin', 'support', 'cas-failures'] as const,
  analyticsOverview:     () => ['admin', 'analytics', 'overview'] as const,
  notificationsHealth:   () => ['admin', 'notifications', 'health'] as const,
} as const;

// ---------------------------------------------------------------------------
// Types — Score Model (Admin.md §14 Score Model)
// ---------------------------------------------------------------------------

export interface AdminScoringRegistryVersion {
  model_version: string;
  created_by: string;
  approved_by: string | null;
  two_person_ok: boolean;
  activated: boolean;
  activated_at: string | null;
  created_at: string;
}

export interface AdminScoringModel {
  model_version: string;
  activated: boolean;
  provisional: boolean;
  methodology_url: string;
  created_by: string;
  axis_weights: Record<string, number>;
  coverage: { total_funds: number };
  registry_versions: AdminScoringRegistryVersion[];
}

// ---------------------------------------------------------------------------
// Types — Feature Flags (Admin.md §14 Feature Flags)
// ---------------------------------------------------------------------------

export interface AdminFlag {
  key: string;
  value: boolean;
  description: string;
  source: string;
  mutable: boolean;
}

// ---------------------------------------------------------------------------
// Types — Support (Admin.md §14 Support)
// ---------------------------------------------------------------------------

export interface AdminCasFailure {
  job_id: string;
  user_id: string;
  status: string;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  support_notes: string | null;
}

// ---------------------------------------------------------------------------
// Types — Analytics (Admin.md §14 Analytics)
// ---------------------------------------------------------------------------

export interface AdminAnalyticsOverview {
  signups_total: number;
  signups_30d: number;
  cas_uploads_total: number;
  cas_uploads_30d: number;
  portfolios_created: number;
  reports_generated: number;
  premium_conversions: number;
  funnel: {
    cas_uploaded: number;
    portfolio_created: number;
    report_generated: number;
  };
  conversion_rate_pct: number;
}

// ---------------------------------------------------------------------------
// Types — Notifications (Admin.md §14 Notifications)
// ---------------------------------------------------------------------------

export interface AdminNotificationsHealth {
  queue_depth: { telegram: number; email: number };
  sent: number;
  failed: number;
  rate_capped: number;
  deferred: number;
  last_sent_at: string | null;
  templates: Array<{ id: string }>;
  broadcast_available: boolean;
}

// ---------------------------------------------------------------------------
// Phase 3 hooks
// ---------------------------------------------------------------------------

export function useAdminScoringModel() {
  return useQuery({
    queryKey: adminKeysP3.scoringModel(),
    queryFn:  () => api.get<AdminScoringModel>('/admin/scoring/model'),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 120 * 1000,
  });
}

export function useAdminFlags() {
  return useQuery({
    queryKey: adminKeysP3.flags(),
    queryFn:  () => api.get<AdminFlag[]>('/admin/flags'),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminCasFailures(limit = 50) {
  return useQuery({
    queryKey: adminKeysP3.supportCasFailures(),
    queryFn:  () => api.get<AdminCasFailure[]>(`/admin/support/cas-failures?limit=${limit}`),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useSetCasNotes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, notes }: { jobId: string; notes: string }) =>
      api.post<{ ok: boolean }>(`/admin/support/cas-failures/${jobId}/notes`, { notes }),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: adminKeysP3.supportCasFailures() });
    },
  });
}

export function useAdminAnalyticsOverview() {
  return useQuery({
    queryKey: adminKeysP3.analyticsOverview(),
    queryFn:  () => api.get<AdminAnalyticsOverview>('/admin/analytics/overview'),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 120 * 1000,
  });
}

export function useAdminNotificationsHealth() {
  return useQuery({
    queryKey: adminKeysP3.notificationsHealth(),
    queryFn:  () => api.get<AdminNotificationsHealth>('/admin/notifications/health'),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Audit hook
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Phase 4 — AI Ops query keys
// ---------------------------------------------------------------------------
export const adminKeysAI = {
  dashboard:  () => ['admin', 'ai', 'dashboard'] as const,
  versions:   () => ['admin', 'ai', 'versions'] as const,
  prompts:    () => ['admin', 'ai', 'prompts'] as const,
  eval:       () => ['admin', 'ai', 'eval'] as const,
  safety:     () => ['admin', 'ai', 'safety'] as const,
  feedback:   () => ['admin', 'ai', 'feedback'] as const,
  cost:       () => ['admin', 'ai', 'cost'] as const,
} as const;

// ---------------------------------------------------------------------------
// Types — AI Ops (Admin.md §15)
// ---------------------------------------------------------------------------

/** Shared budget snapshot — mirrors BudgetSnapshot in aiops_schemas.py */
export interface AdminAIBudget {
  free_calls_today: number;
  free_cap: number;
  premium_usd_today: number;
  premium_soft_cap: number;
  premium_hard_cap: number;
  free_remaining: number;
  premium_remaining_usd: number;
}

/** Mirrors LabelChurnSummary in aiops_schemas.py */
export interface AdminAILabelChurn {
  decision: string;
  churn: number;
  requires_human_review: boolean;
  reason: string | null;
}

/** Mirrors InstrumentedFalse in aiops_schemas.py */
export interface AdminAIInstrumented {
  instrumented: boolean;
  note?: string;
}

/** Mirrors GroundednessInfo in aiops_schemas.py — sampled LLM-judge groundedness. */
export interface AdminAIGroundedness {
  instrumented: boolean;
  value: number | null;
  sample_count: number;
  low_flags: number;
  window_days: number;
  note?: string;
}

/** Mirrors LatencyInfo in aiops_schemas.py — rolling avg LLM response latency. */
export interface AdminAILatency {
  instrumented: boolean;
  value_ms: number | null;
  sample_count: number;
  window_days: number;
  note?: string;
}

/** Mirrors ModelSpendRow in aiops_schemas.py */
export interface AdminAIModelSpendRow {
  model: string;
  calls: number;
  usd: number;
}

/** Mirrors PerModelSpend in aiops_schemas.py — per-model AI spend breakdown. */
export interface AdminAIPerModel {
  instrumented: boolean;
  window_days: number;
  models: AdminAIModelSpendRow[];
  total_calls: number;
  total_usd: number;
  note?: string;
}

/** Mirrors AiDashboardResponse in aiops_schemas.py */
export interface AdminAIDashboard {
  model_version: string;
  activated: boolean;
  budget: AdminAIBudget;
  served_7d: number;
  low_confidence_7d: number;
  label_churn: AdminAILabelChurn;
  avg_latency_ms: AdminAILatency;
  eval_score: AdminAIGroundedness;
}

/** Per-version backtest JSONB: {"passed": bool} written at activation (PR-5). */
export interface AdminAIBacktestRow {
  passed?: boolean;
  [k: string]: unknown;
}

/** Mirrors EngineVersionRow in aiops_schemas.py */
export interface AdminAIRegistryVersion {
  model_version: string;
  created_by: string | null;
  approved_by: string | null;
  two_person_ok: boolean;
  activated: boolean;
  activated_at: string | null;
  created_at: string | null;
  backtest: AdminAIBacktestRow | null;
  drift: Record<string, unknown> | null;
}

/** Mirrors BacktestStatus in aiops_schemas.py */
export interface AdminAIBacktest {
  instrumented: boolean;
  versions_with_backtest: number;
  note: string;
}

/** Mirrors DriftStatus in aiops_schemas.py */
export interface AdminAIDrift {
  instrumented: boolean;
  decision: string;
  churn: number;
  requires_human_review: boolean;
  note: string;
}

/** Mirrors AiVersionsResponse in aiops_schemas.py */
export interface AdminAIVersions {
  versions: AdminAIRegistryVersion[];
  backtest: AdminAIBacktest;
  drift: AdminAIDrift;
}

/** Mirrors AiPromptsResponse in aiops_schemas.py */
export interface AdminAIPrompts {
  registry: boolean;
  note: string;
  prompt_versions_seen: string[];
}

/** Mirrors QualityIssueRow in aiops_schemas.py (same shape as AdminQualityIssue) */
export interface AdminAIQualityIssueRow {
  metric_key: string;
  label: string;
  current_value: number | null;
  threshold: number | null;
  unit: string;
  status: string;
  acknowledged_until: string | null;
}

/** Mirrors AiEvalResponse in aiops_schemas.py */
export interface AdminAIEval {
  quality_issues: AdminAIQualityIssueRow[];
  groundedness: AdminAIGroundedness;
}

/** Mirrors AuditRowSummary in aiops_schemas.py */
export interface AdminAIAuditRow {
  id: string;
  served_at: string | null;
  recommendation_type: string;
  label: string | null;
  confidence_band: string | null;
  model: string | null;
  surface: string | null;
  prompt_version: string | null;
  request_id: string | null;
}

/** Mirrors LowConfidenceRowSummary in aiops_schemas.py */
export interface AdminAILowConfRow {
  id: string;
  logged_at: string | null;
  surface: string | null;
  identifier: string | null;
  confidence_score: number | null;
  confidence_band: string | null;
  model: string | null;
  reason: string | null;
  request_id: string | null;
}

/** Mirrors AdviceBoundaryBreachesInfo in aiops_schemas.py */
export interface AdminAIBreachInfo {
  value: number;
  window_days: number;
  instrumented: boolean;
  note: string;
}

/** Mirrors AiSafetyResponse in aiops_schemas.py */
export interface AdminAISafety {
  days: number;
  served_by_type: Record<string, number>;
  by_confidence_band: Record<string, number>;
  low_confidence_count: number;
  recent_audit_rows: AdminAIAuditRow[];
  recent_low_confidence: AdminAILowConfRow[];
  label_churn_educational: AdminAILabelChurn;
  label_churn_mood: AdminAILabelChurn;
  advice_boundary_breaches: AdminAIBreachInfo;
  groundedness: AdminAIGroundedness;
}

/** Mirrors AiFeedbackResponse in aiops_schemas.py */
export interface AdminAIFeedback {
  available: boolean;
  note: string;
}

/** Mirrors AiCostResponse in aiops_schemas.py (budget nested) */
export interface AdminAICost {
  budget: AdminAIBudget;
  per_model: AdminAIPerModel;
  latency: AdminAILatency;
}

// ---------------------------------------------------------------------------
// AI Ops hooks
// ---------------------------------------------------------------------------

export function useAdminAIDashboard() {
  return useQuery({
    queryKey: adminKeysAI.dashboard(),
    queryFn:  () => api.get<AdminAIDashboard>('/admin/ai'),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminAIVersions() {
  return useQuery({
    queryKey: adminKeysAI.versions(),
    queryFn:  () => api.get<AdminAIVersions>('/admin/ai/versions'),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 120 * 1000,
  });
}

export function useAdminAIPrompts() {
  return useQuery({
    queryKey: adminKeysAI.prompts(),
    queryFn:  () => api.get<AdminAIPrompts>('/admin/ai/prompts'),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 120 * 1000,
  });
}

export function useAdminAIEval() {
  return useQuery({
    queryKey: adminKeysAI.eval(),
    queryFn:  () => api.get<AdminAIEval>('/admin/ai/eval'),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 120 * 1000,
  });
}

export function useAdminAISafety() {
  return useQuery({
    queryKey: adminKeysAI.safety(),
    queryFn:  () => api.get<AdminAISafety>('/admin/ai/safety'),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useAdminAIFeedback() {
  return useQuery({
    queryKey: adminKeysAI.feedback(),
    queryFn:  () => api.get<AdminAIFeedback>('/admin/ai/feedback'),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 120 * 1000,
  });
}

export function useAdminAICost() {
  return useQuery({
    queryKey: adminKeysAI.cost(),
    queryFn:  () => api.get<AdminAICost>('/admin/ai/cost'),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// User mutations — Phase 5 first slice
// ---------------------------------------------------------------------------

export function useSuspendUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      api.post<{ ok: boolean; status: string }>(`/admin/users/${id}/suspend`, reason ? { reason } : {}),
    onSettled: (_data, _err, { id }) => {
      qc.invalidateQueries({ queryKey: adminKeysExt.users() });
      qc.invalidateQueries({ queryKey: adminKeysExt.userSummary() });
      qc.invalidateQueries({ queryKey: adminKeysExt.user(id) });
    },
  });
}

export function useUnsuspendUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<{ ok: boolean; status: string }>(`/admin/users/${id}/unsuspend`),
    onSettled: (_data, _err, id) => {
      qc.invalidateQueries({ queryKey: adminKeysExt.users() });
      qc.invalidateQueries({ queryKey: adminKeysExt.userSummary() });
      qc.invalidateQueries({ queryKey: adminKeysExt.user(id) });
    },
  });
}

// ---------------------------------------------------------------------------
// Phase 5 — Users mutations (reset-access added)
// ---------------------------------------------------------------------------

export function useResetUserAccess() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<{ ok: boolean }>(`/admin/users/${id}/reset-access`),
    onSettled: (_data, _err, id) => {
      qc.invalidateQueries({ queryKey: adminKeysExt.users() });
      qc.invalidateQueries({ queryKey: adminKeysExt.user(id) });
    },
  });
}

// ---------------------------------------------------------------------------
// Phase 5 — Billing mutations
// ---------------------------------------------------------------------------

export interface RefundPayload {
  razorpay_payment_id: string;
  amount_inr: number;
  reason: string;
}

export interface PlanChangePayload {
  tier: string;
  grant_until?: string | null;
  reason: string;
}

export function useAdminRefund() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ payload, idempotencyKey }: { payload: RefundPayload; idempotencyKey: string }) =>
      api.postH<{ ok: boolean }>('/admin/billing/refund', payload, { 'Idempotency-Key': idempotencyKey }),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: adminKeysExt.billingPayments() });
      qc.invalidateQueries({ queryKey: adminKeysExt.billingOverview() });
    },
  });
}

export function useAdminPlanChange() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, payload }: { userId: string; payload: PlanChangePayload }) =>
      api.post<{ ok: boolean }>(`/admin/billing/users/${userId}/plan`, payload),
    onSettled: (_data, _err, { userId }) => {
      qc.invalidateQueries({ queryKey: adminKeysExt.users() });
      qc.invalidateQueries({ queryKey: adminKeysExt.user(userId) });
      qc.invalidateQueries({ queryKey: adminKeysExt.billingOverview() });
    },
  });
}

// ---------------------------------------------------------------------------
// Phase 5 — AI Ops mutations
// ---------------------------------------------------------------------------

export interface CreatePromptVersionPayload {
  template_key: string;
  body: string;
  notes?: string;
}

export interface SetBudgetCapsPayload {
  free_cap: number;
  premium_soft_usd: number;
  premium_hard_usd: number;
  reset?: boolean;
}

export function useAdminCreatePromptVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreatePromptVersionPayload) =>
      api.post<{ ok: boolean; version?: string }>('/admin/ai/prompts', payload),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: adminKeysAI.prompts() });
    },
  });
}

export function useAdminActivatePromptVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, version }: { key: string; version: string }) =>
      api.post<{ ok: boolean }>(`/admin/ai/prompts/${key}/${version}/activate`),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: adminKeysAI.prompts() });
      qc.invalidateQueries({ queryKey: adminKeysAI.dashboard() });
    },
  });
}

export function useAdminSetBudgetCaps() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SetBudgetCapsPayload) =>
      api.post<{ ok: boolean }>('/admin/ai/cost/caps', payload),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: adminKeysAI.cost() });
      qc.invalidateQueries({ queryKey: adminKeysAI.dashboard() });
    },
  });
}

// ---------------------------------------------------------------------------
// Phase 5 — Notifications broadcast mutation
// ---------------------------------------------------------------------------

export interface BroadcastPayload {
  title: string;
  body: string;
  channel: 'telegram_public';
}

export function useAdminBroadcast() {
  return useMutation({
    mutationFn: ({ payload, idempotencyKey }: { payload: BroadcastPayload; idempotencyKey: string }) =>
      api.postH<{ ok: boolean; queued?: number }>('/admin/notifications/broadcast', payload, {
        'Idempotency-Key': idempotencyKey,
      }),
  });
}

// ---------------------------------------------------------------------------
// Phase 5 — Scoring activation mutation
// ---------------------------------------------------------------------------

export interface ActivateScoringPayload {
  backtest_passed: boolean;
}

export function useAdminActivateScoringVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ version, payload }: { version: string; payload: ActivateScoringPayload }) =>
      api.post<{ ok: boolean; model_version?: string }>(`/admin/scoring/${version}/activate`, payload),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: adminKeysP3.scoringModel() });
    },
  });
}

// ---------------------------------------------------------------------------
// Audit hook
// ---------------------------------------------------------------------------

export function useAdminAudit(params?: {
  since?: string;
  until?: string;
  action?: string;
  admin_id?: string;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  if (params?.since)    qs.set('since',    params.since);
  if (params?.until)    qs.set('until',    params.until);
  if (params?.action)   qs.set('action',   params.action);
  if (params?.admin_id) qs.set('admin_id', params.admin_id);
  if (params?.limit)    qs.set('limit',    String(params.limit));
  if (params?.offset)   qs.set('offset',   String(params.offset));
  const path = `/admin/audit${qs.toString() ? '?' + qs.toString() : ''}`;
  return useQuery({
    queryKey: adminKeysExt.audit(params),
    queryFn: () => api.get<AdminAuditRow[]>(path),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

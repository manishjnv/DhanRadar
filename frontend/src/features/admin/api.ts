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
  all:     () => ['admin'] as const,
  health:  () => ['admin', 'health'] as const,
  sources: () => ['admin', 'sources'] as const,
  tasks:   () => ['admin', 'tasks'] as const,
  runs:    (params?: Record<string, unknown>) => ['admin', 'runs', params] as const,
  run:     (id: string) => ['admin', 'run', id] as const,
  quality: () => ['admin', 'quality'] as const,
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
  run_id: string;
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

export function useAdminSources() {
  return useQuery({
    queryKey: adminKeys.sources(),
    queryFn: () => api.get<AdminSource[]>('/admin/sources'),
    staleTime: 30 * 1000,
  });
}

export function useAdminTasks() {
  return useQuery({
    queryKey: adminKeys.tasks(),
    queryFn: () => api.get<AdminTask[]>('/admin/tasks'),
    staleTime: 30 * 1000,
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

// frontend/src/features/signal/api.ts
/**
 * Signal feature — TanStack Query hooks.
 * All authenticated endpoints use credentials:'include' via apiClient (no bearer header).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type {
  BreadthData,
  JournalEntryCreate,
  JournalResponse,
  LearningContentResponse,
  NotificationsResponse,
  SignalDeployment,
  SignalDipFund,
  SignalRules,
  SignalStateResponse,
  VIXData,
} from './types';

function signalRetry(count: number, error: unknown): boolean {
  if (error instanceof ApiError && error.problem.status === 404) return false;
  return count < 1;
}

// ---------------------------------------------------------------------------
// Server-computed signal state (compliance: weights + score never sent to client)
// ---------------------------------------------------------------------------
export function useSignalState() {
  return useQuery({
    queryKey: queryKeys.signal.state(),
    queryFn: () => api.get<SignalStateResponse>('/signal/state'),
    retry: signalRetry,
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Signal rules (user thresholds)
// ---------------------------------------------------------------------------
export function useSignalRules() {
  return useQuery({
    queryKey: queryKeys.signal.rules(),
    queryFn: () => api.get<SignalRules>('/signal/rules'),
    retry: signalRetry,
    staleTime: 5 * 60 * 1000,
  });
}

export function useSaveSignalRules() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rules: SignalRules) => api.put<SignalRules>('/signal/rules', rules),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: queryKeys.signal.rules() }),
  });
}

// ---------------------------------------------------------------------------
// Dip fund
// ---------------------------------------------------------------------------
export function useSignalDipFund() {
  return useQuery({
    queryKey: queryKeys.signal.dipFund(),
    queryFn: () => api.get<SignalDipFund>('/signal/dip-fund'),
    retry: signalRetry,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAddDipFund() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (amount: number) =>
      api.post<SignalDipFund>('/signal/dip-fund/add', { amount }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: queryKeys.signal.dipFund() }),
  });
}

// ---------------------------------------------------------------------------
// Deployments
// ---------------------------------------------------------------------------
export function useSignalDeployments() {
  return useQuery({
    queryKey: queryKeys.signal.deployments(),
    queryFn: () => api.get<SignalDeployment[]>('/signal/deployments'),
    retry: signalRetry,
    staleTime: 5 * 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Market data (60s polling during market hours)
// ---------------------------------------------------------------------------
export function useVIX() {
  return useQuery({
    queryKey: queryKeys.vix.current(),
    queryFn: () => api.get<VIXData>('/market/vix'),
    retry: 1,
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useBreadth() {
  return useQuery({
    queryKey: queryKeys.breadth.current(),
    queryFn: () => api.get<BreadthData>('/market/breadth'),
    retry: 1,
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Journal (Phase 2 — Reflect tab)
// ---------------------------------------------------------------------------
export function useJournal() {
  return useQuery({
    queryKey: queryKeys.signal.journal(),
    queryFn: () => api.get<JournalResponse>('/signal/journal'),
    retry: signalRetry,
    staleTime: 2 * 60 * 1000,
  });
}

export function useAddJournal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entry: JournalEntryCreate) =>
      api.post<{ id: string; created_at: string }>('/signal/journal', entry),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: queryKeys.signal.journal() }),
  });
}

export function useDeleteJournal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entryId: string) => api.del<void>(`/signal/journal/${entryId}`),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: queryKeys.signal.journal() }),
  });
}

// ---------------------------------------------------------------------------
// Learning content (Phase 3 Part A)
// ---------------------------------------------------------------------------
export function useLearningContent(signalState: string) {
  return useQuery({
    queryKey: queryKeys.signal.learning(signalState),
    queryFn: () =>
      api.get<LearningContentResponse>(`/signal/learning?signal_state=${signalState}`),
    retry: signalRetry,
    staleTime: 10 * 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Notifications (Phase 3 Part B)
// ---------------------------------------------------------------------------
export function useNotifications() {
  return useQuery({
    queryKey: queryKeys.signal.notifications(),
    queryFn: () => api.get<NotificationsResponse>('/signal/notifications'),
    retry: signalRetry,
    staleTime: 60 * 1000,
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<void>(`/signal/notifications/${id}/read`, {}),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: queryKeys.signal.notifications() }),
  });
}

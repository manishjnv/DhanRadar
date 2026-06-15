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
  SignalDeployment,
  SignalDipFund,
  SignalRules,
  VIXData,
} from './types';

function signalRetry(count: number, error: unknown): boolean {
  if (error instanceof ApiError && error.problem.status === 404) return false;
  return count < 1;
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

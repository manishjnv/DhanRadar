/**
 * Consent feature — TanStack Query hooks.
 *
 * All calls go through apiClient (cookie auth, /api/v1 base, RFC7807 errors,
 * one silent /auth/refresh on 401). No token is ever read or stored in JS —
 * the session lives entirely in HttpOnly __Host-* cookies.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type { ConsentPurpose, ConsentState } from './types';

// ---------------------------------------------------------------------------
// useConsent — current consent state. A 401 means "anonymous" (normal state).
// Don't spin retries on it — mirrors the useMe / useNotificationPreferences pattern.
// ---------------------------------------------------------------------------
export function useConsent() {
  return useQuery<ConsentState>({
    queryKey: queryKeys.consent.state(),
    queryFn: () => api.get<ConsentState>('/consent'),
    retry: (count, error) => {
      if (error instanceof ApiError && error.problem.status === 401) return false;
      return count < 1;
    },
    staleTime: 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// useGrantConsent — POST /consent/grant { purposes: string[] }
// On success, seeds the consent query cache with the authoritative server state.
// ---------------------------------------------------------------------------
export function useGrantConsent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { purposes: ConsentPurpose[] }) =>
      api.post<ConsentState>('/consent/grant', payload),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.consent.state(), data);
    },
  });
}

// ---------------------------------------------------------------------------
// useRevokeConsent — POST /consent/revoke { purposes: string[] }
// On success, seeds the consent query cache with the authoritative server state.
// ---------------------------------------------------------------------------
export function useRevokeConsent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { purposes: ConsentPurpose[] }) =>
      api.post<ConsentState>('/consent/revoke', payload),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.consent.state(), data);
    },
  });
}

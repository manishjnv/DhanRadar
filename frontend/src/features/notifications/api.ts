/**
 * Notification feature — TanStack Query hooks.
 *
 * All calls go through apiClient (cookie auth, /api/v1 base, RFC7807 errors).
 * No Authorization header is ever added — auth is HttpOnly cookie-only.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type {
  PreferencesResponse,
  PreferencesUpdate,
  TestNotificationRequest,
  TestNotificationResponse,
} from './types';

// ---------------------------------------------------------------------------
// useNotificationPreferences — load the current preferences.
// 401 means unauthenticated (normal state at this route); don't retry on it.
// ---------------------------------------------------------------------------
export function useNotificationPreferences() {
  return useQuery<PreferencesResponse>({
    queryKey: queryKeys.notifications.preferences(),
    queryFn: () => api.get<PreferencesResponse>('/notifications/preferences'),
    retry: (count, error) => {
      if (error instanceof ApiError && error.problem.status === 401) return false;
      return count < 1;
    },
    staleTime: 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// useUpdateNotificationPreferences — partial PATCH-style POST.
// Only allowed keys (PreferencesUpdate) are ever sent; the mutation caller is
// responsible for computing the diff. On success, seeds the query cache so the
// screen reflects the authoritative server state immediately.
// ---------------------------------------------------------------------------
export function useUpdateNotificationPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (update: PreferencesUpdate) =>
      api.post<PreferencesResponse>('/notifications/preferences', update),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.notifications.preferences(), data);
    },
  });
}

// ---------------------------------------------------------------------------
// useSendTestNotification — Pro-tier only; caller must gate on tier before
// calling. 402 = tier_required, 400 = telegram_not_set.
// ---------------------------------------------------------------------------
export function useSendTestNotification() {
  return useMutation({
    mutationFn: (req: TestNotificationRequest) =>
      api.post<TestNotificationResponse>('/notifications/test', req),
  });
}

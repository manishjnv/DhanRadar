/**
 * Auth feature — TanStack Query hooks.
 *
 * All calls go through apiClient (cookie auth, /api/v1 base, RFC7807 errors,
 * one silent /auth/refresh on 401). No token is ever read or stored in JS —
 * the session lives entirely in HttpOnly __Host-* cookies.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type { AuthEnvelope, AuthUser, Credentials, MeEnvelope } from './types';

// ---------------------------------------------------------------------------
// useMe — current session. The cookie is the source of truth; a 401 means
// "anonymous", which is a normal state, not an error to retry.
// ---------------------------------------------------------------------------
export function useMe() {
  return useQuery<AuthUser>({
    queryKey: queryKeys.auth.me(),
    queryFn: async () => {
      const res = await api.get<MeEnvelope>('/auth/me');
      return res.user;
    },
    // apiClient already attempts one silent refresh on 401; if it still 401s
    // the user is genuinely anonymous — don't spin retries on that.
    retry: (count, error) => {
      if (error instanceof ApiError && error.problem.status === 401) return false;
      return count < 1;
    },
    staleTime: 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// useLogin / useSignup — set cookies server-side, then seed the me cache so
// the guard and topbar update without an extra round-trip.
// ---------------------------------------------------------------------------
export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (creds: Credentials) =>
      api.post<AuthEnvelope>('/auth/login', creds),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.auth.me(), data.user);
    },
  });
}

export function useSignup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (creds: Credentials) =>
      api.post<AuthEnvelope>('/auth/signup', creds),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.auth.me(), data.user);
    },
  });
}

// ---------------------------------------------------------------------------
// useLogout — server revokes the refresh jti + denylists the access jti and
// clears cookies; we then wipe the client cache so no stale user data lingers.
// ---------------------------------------------------------------------------
export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ message: string }>('/auth/logout'),
    onSettled: () => {
      // Clear regardless of outcome — cookies may already be gone.
      qc.setQueryData(queryKeys.auth.me(), null);
      qc.clear();
    },
  });
}

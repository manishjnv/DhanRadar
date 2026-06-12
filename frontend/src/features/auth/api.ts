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
import type {
  AuthEnvelope,
  AuthUser,
  Credentials,
  EmailOtpCredentials,
  EmailOtpRequestBody,
  EmailOtpRequestResponse,
  MeEnvelope,
  TotpCredentials,
  TotpSetupResponse,
  TotpVerifyRequest,
} from './types';

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
// useTotpLogin — sign in with a TOTP code instead of a password.
// Mirrors useLogin exactly: POST /auth/totp/login, then seeds the me cache.
// The 401 from this endpoint is intentionally uniform ("invalid_credentials")
// regardless of whether the email is unknown, not enrolled, or code is wrong.
// ---------------------------------------------------------------------------
export function useTotpLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (creds: TotpCredentials) =>
      api.post<AuthEnvelope>('/auth/totp/login', creds),
    onSuccess: (data) => {
      // Seed the me cache BEFORE the caller navigates — same seeding order as
      // useLogin (RCA: AuthGuard reads stale cache if navigation fires first).
      qc.setQueryData(queryKeys.auth.me(), data.user);
    },
  });
}

// ---------------------------------------------------------------------------
// useRequestEmailOtp — fire POST /auth/email-otp/request. The backend always
// returns 202 {"message":"otp_sent_if_account_exists"} to prevent enumeration;
// 503 means the feature is unconfigured; 429 on rate limit.
// ---------------------------------------------------------------------------
export function useRequestEmailOtp() {
  return useMutation({
    mutationFn: (body: EmailOtpRequestBody) =>
      api.post<EmailOtpRequestResponse>('/auth/email-otp/request', body),
  });
}

// ---------------------------------------------------------------------------
// useEmailOtpLogin — sign in with email + 6-digit OTP code.
// Mirrors useTotpLogin exactly: POST /auth/email-otp/login, seeds me cache.
// The 401 from this endpoint is intentionally uniform regardless of failure
// reason (expired code, wrong code, unknown email) — no enumeration signal.
// ---------------------------------------------------------------------------
export function useEmailOtpLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (creds: EmailOtpCredentials) =>
      api.post<AuthEnvelope>('/auth/email-otp/login', creds),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.auth.me(), data.user);
    },
  });
}

// ---------------------------------------------------------------------------
// useTotpSetup — initiate TOTP enrollment; returns provisioning_uri + secret.
// Authenticated route — only call when the user is already logged in.
// ---------------------------------------------------------------------------
export function useTotpSetup() {
  return useMutation({
    mutationFn: () =>
      api.post<TotpSetupResponse>('/auth/totp/setup'),
  });
}

// ---------------------------------------------------------------------------
// useTotpVerify — confirm the TOTP code to activate TOTP on the account.
// On success the caller should invalidate queryKeys.auth.me() so totp_verified
// flips to true in the me cache.
// ---------------------------------------------------------------------------
export function useTotpVerify() {
  return useMutation({
    mutationFn: (req: TotpVerifyRequest) =>
      api.post<{ message: string }>('/auth/totp/verify', req),
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

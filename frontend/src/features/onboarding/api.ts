/**
 * Onboarding feature — TanStack Query hooks.
 *
 * All calls go through apiClient (cookie auth, /api/v1 base, RFC7807 errors,
 * one silent /auth/refresh on 401). No token is ever read or stored in JS —
 * the session lives entirely in HttpOnly __Host-* cookies.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type { RiskQuizRequest, RiskQuizResponse } from './types';

// ---------------------------------------------------------------------------
// useSubmitRiskQuiz — POST /onboarding/risk-quiz { answers: number[] }
// On success, seed the now-set risk_profile into the auth.me cache, THEN
// invalidate. The seed matters: the page navigates to /mf/portfolio immediately
// in onComplete, and AuthGuard reads risk_profile synchronously — if we only
// invalidated, the in-flight refetch still holds the stale null and the guard
// bounces the user back to /onboarding (the quiz shows a second time). The
// response carries the canonical normalised label, so the seed is authoritative.
// ---------------------------------------------------------------------------
export function useSubmitRiskQuiz() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: RiskQuizRequest) =>
      api.post<RiskQuizResponse>('/onboarding/risk-quiz', payload),
    onSuccess: (data) => {
      // Patch just risk_profile on the cached me object. Typed structurally (not
      // via the auth feature's AuthUser) to respect feature isolation (#7); the
      // runtime spread preserves every other field of the real cached user.
      qc.setQueryData<{ risk_profile: string | null } | null>(
        queryKeys.auth.me(),
        (prev) => (prev ? { ...prev, risk_profile: data.risk_profile } : prev),
      );
      void qc.invalidateQueries({ queryKey: queryKeys.auth.me() });
    },
  });
}

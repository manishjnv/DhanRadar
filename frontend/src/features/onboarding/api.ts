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
// On success, invalidates the auth.me query so AuthGuard re-reads the
// now-set risk_profile and the cold-start redirect resolves.
// ---------------------------------------------------------------------------
export function useSubmitRiskQuiz() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: RiskQuizRequest) =>
      api.post<RiskQuizResponse>('/onboarding/risk-quiz', payload),
    onSuccess: () => {
      // Invalidate rather than set — the server is authoritative on the
      // normalised risk_profile value; refetch gives us the canonical shape.
      void qc.invalidateQueries({ queryKey: queryKeys.auth.me() });
    },
  });
}

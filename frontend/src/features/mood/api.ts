/**
 * Mood feature — TanStack Query hooks.
 * All endpoints are ANONYMOUS (public, no auth required).
 * All calls go through apiClient (credentials:'include', /api/v1 base, RFC7807 errors).
 * NEVER add an Authorization header (architecture non-negotiable #5).
 */
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type { MoodPublic, MoodHistoryItem, WhyToday } from './types';

// ---------------------------------------------------------------------------
// Retry helper — 404 means "no snapshot yet", not a transient error; don't retry.
// ---------------------------------------------------------------------------
function moodRetry(count: number, error: unknown): boolean {
  if (error instanceof ApiError && error.problem.status === 404) return false;
  return count < 1;
}

// ---------------------------------------------------------------------------
// GET /market/mood — current snapshot
// ---------------------------------------------------------------------------
export function useMoodCurrent() {
  return useQuery({
    queryKey: queryKeys.mood.current(),
    queryFn:  () => api.get<MoodPublic>('/market/mood'),
    retry:    moodRetry,
    staleTime: 5 * 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// GET /market/mood/history?days=N
// ---------------------------------------------------------------------------
export function useMoodHistory(days: number = 30) {
  return useQuery({
    queryKey: queryKeys.mood.history(days),
    queryFn:  () => api.get<MoodHistoryItem[]>(`/market/mood/history?days=${days}`),
    retry:    moodRetry,
    staleTime: 5 * 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// GET /market/indices — public index levels (Nifty 50, Sensex, …).
// `value`/`change_pct` are PUBLIC market data, explicitly allowed in the DOM
// (NOT the proprietary mood score). Public endpoint, no auth.
// ---------------------------------------------------------------------------
export interface MarketIndex {
  name: string;
  value: number;
  change_pct: number;
}

export function useMarketIndices() {
  return useQuery({
    queryKey: ['market', 'indices'],
    queryFn: () => api.get<MarketIndex[]>('/market/indices'),
    retry: moodRetry,
    staleTime: 5 * 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// GET /market/why-today
// ---------------------------------------------------------------------------
export function useWhyToday() {
  return useQuery({
    queryKey: queryKeys.mood.whyToday(),
    queryFn:  () => api.get<WhyToday>('/market/why-today'),
    retry:    moodRetry,
    staleTime: 5 * 60 * 1000,
  });
}

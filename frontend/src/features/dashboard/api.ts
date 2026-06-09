/**
 * Dashboard feature — TanStack Query hooks.
 */
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface MarketIndex {
  name: string;
  /** Public market index value — allowed in DOM */
  value: number;
  change_pct: number;
}

export interface TopScoredFund {
  isin: string;
  scheme_name: string;
  category: string;
  /** Non-advisory label */
  label: Label;
  confidence_band: ConfidenceBand;
}

export interface TopScoredResponse {
  funds: TopScoredFund[];
  /** Backend-supplied disclosure string (must be rendered adjacent to labels) */
  disclosure: string;
  /** Backend-supplied not_advice string */
  not_advice: string;
  disclaimer_version: string;
}

export interface NewsItem {
  id: string;
  title: string;
  source: string;
  freshness: string;
}

export interface PortfolioFund {
  isin: string;
  scheme_name: string;
  /** Non-advisory label */
  label: Label;
  confidence_band: ConfidenceBand;
}

export interface PortfolioSummary {
  /** User's own money — allowed in DOM */
  current_value: number | null;
  xirr_pct: number | null;
  fund_count: number;
  last_updated: string | null;
  funds: PortfolioFund[];
  /** Backend-supplied disclosure string (must be rendered adjacent to labels) */
  disclosure: string;
  /** Backend-supplied not_advice string */
  not_advice: string;
  disclaimer_version: string;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------
export function useIndices() {
  return useQuery({
    queryKey: queryKeys.indices.all(),
    queryFn: () => api.get<MarketIndex[]>('/indices'),
    staleTime: 60 * 1000,
  });
}

export function useTopScored() {
  return useQuery({
    queryKey: queryKeys.instruments.topScored('fund'),
    queryFn: () => api.get<TopScoredResponse>('/instruments/top-scored?type=fund'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useMarketNews() {
  return useQuery({
    queryKey: queryKeys.news.feed({ scope: 'market' }),
    queryFn: () => api.get<NewsItem[]>('/news?scope=market'),
    staleTime: 5 * 60 * 1000,
  });
}

export function usePortfolioSummary() {
  return useQuery({
    queryKey: queryKeys.portfolio.summary(),
    queryFn: () => api.get<PortfolioSummary>('/portfolio/summary'),
    // 404 = no portfolio yet (cold start) — treat as empty, don't retry
    retry: (count, error) => {
      if (error instanceof ApiError && error.problem.status === 404) return false;
      return count < 1;
    },
    staleTime: 60 * 1000,
  });
}

/**
 * News feature — TanStack Query hooks.
 *
 * Moved out of features/dashboard (dashboard decommissioned) since the market
 * news widget now lives on the public Market Mood page — /news is anonymous-allowed.
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface NewsItem {
  title: string;
  source: string;
  url: string;
  published_at: string;
  category: string;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------
export function useMarketNews() {
  return useQuery({
    queryKey: queryKeys.news.feed({ scope: 'market' }),
    queryFn: () => api.get<NewsItem[]>('/news?scope=market&limit=5'),
    staleTime: 5 * 60 * 1000,
  });
}

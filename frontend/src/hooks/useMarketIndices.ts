import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';

export interface MarketIndex {
  name: string;
  value: number;
  change_pct: number;
}

export function useMarketIndices() {
  return useQuery({
    queryKey: queryKeys.indices.all(),
    queryFn: () => api.get<MarketIndex[]>('/indices'),
    staleTime: 60 * 1000,
  });
}

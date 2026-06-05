/**
 * queryKeys — TanStack Query key factory
 * Centralised so key shape is never duplicated across features.
 */
export const queryKeys = {
  instruments: {
    all:       () => ['instruments'] as const,
    list:      (params?: Record<string, unknown>) => ['instruments', 'list', params] as const,
    detail:    (symbol: string) => ['instruments', symbol] as const,
    score:     (symbol: string) => ['instruments', symbol, 'score'] as const,
    topScored: (type?: string) => ['instruments', 'top-scored', type] as const,
  },
  scores: {
    all:    () => ['scores'] as const,
    detail: (symbol: string) => ['scores', symbol] as const,
  },
  portfolio: {
    all:     () => ['portfolio'] as const,
    detail:  (id: string) => ['portfolio', id] as const,
    summary: () => ['portfolio', 'summary'] as const,
  },
  watchlists: {
    all:    () => ['watchlists'] as const,
    detail: (id: string) => ['watchlists', id] as const,
  },
  alerts: {
    all:    () => ['alerts'] as const,
    detail: (id: string) => ['alerts', id] as const,
  },
  ai: {
    all:     () => ['ai'] as const,
    insight: (symbol: string) => ['ai', 'insight', symbol] as const,
  },
  news: {
    all:    () => ['news'] as const,
    feed:   (params?: Record<string, unknown>) => ['news', 'feed', params] as const,
    detail: (id: string) => ['news', id] as const,
  },
  indices: {
    all: () => ['indices'] as const,
  },
  mf: {
    casStatus: (jobId: string) => ['mf', 'cas-status', jobId] as const,
    report:    (jobId: string) => ['mf', 'report', jobId] as const,
  },
} as const;

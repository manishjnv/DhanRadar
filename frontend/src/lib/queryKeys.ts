/**
 * queryKeys — TanStack Query key factory
 * Centralised so key shape is never duplicated across features.
 */
export const queryKeys = {
  auth: {
    me: () => ['auth', 'me'] as const,
  },
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
    all:           () => ['portfolio'] as const,
    detail:        (id: string) => ['portfolio', id] as const,
    summary:       () => ['portfolio', 'summary'] as const,
    overlap:       (portfolioId: string) => ['portfolio', portfolioId, 'overlap'] as const,
    concentration: (portfolioId: string) => ['portfolio', portfolioId, 'concentration'] as const,
    changes:       (portfolioId: string) => ['portfolio', portfolioId, 'changes'] as const,
    transparency:  (portfolioId: string) => ['portfolio', portfolioId, 'transparency'] as const,
    moodContext:   (portfolioId: string) => ['portfolio', portfolioId, 'mood-context'] as const,
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
    casStatus:          (jobId: string) => ['mf', 'cas-status', jobId] as const,
    report:             (jobId: string) => ['mf', 'report', jobId] as const,
    explorerCategories: ()              => ['mf', 'explorer', 'categories'] as const,
    explorerFunds:      (params: { category: string; sort: string; sortDir?: string; planType?: string; optionType?: string; page: number; limit?: number }) =>
                          ['mf', 'explorer', 'funds', params] as const,
    fundDetail:         (isin: string, category: string) =>
                          ['mf', 'fund-detail', isin, category] as const,
  },
  notifications: {
    preferences: () => ['notifications', 'preferences'] as const,
  },
  mood: {
    current:  () => ['mood', 'current'] as const,
    history:  (days: number) => ['mood', 'history', days] as const,
    whyToday: () => ['mood', 'why-today'] as const,
  },
  consent: {
    state: () => ['consent', 'state'] as const,
  },
  signal: {
    rules:         () => ['signal', 'rules'] as const,
    dipFund:       () => ['signal', 'dip-fund'] as const,
    deployments:   () => ['signal', 'deployments'] as const,
    journal:       () => ['signal', 'journal'] as const,
    learning:      (state: string) => ['signal', 'learning', state] as const,
    notifications: () => ['signal', 'notifications'] as const,
  },
  vix: {
    current: () => ['market', 'vix'] as const,
  },
  breadth: {
    current: () => ['market', 'breadth'] as const,
  },
} as const;

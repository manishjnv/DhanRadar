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
    summaryById:   (id: string) => ['portfolio', id, 'summary'] as const,
    holdings:      (id: string) => ['portfolio', id, 'holdings'] as const,
    transactions:  (portfolioId: string, isin?: string) => ['portfolio', portfolioId, 'transactions', isin ?? 'all'] as const,
    allocation:    (portfolioId: string, by = 'category') => ['portfolio', portfolioId, 'allocation', by] as const,
    concentration: (portfolioId: string) => ['portfolio', portfolioId, 'concentration'] as const,
    diversification: (portfolioId: string) => ['portfolio', portfolioId, 'diversification'] as const,
    risk:          (portfolioId: string) => ['portfolio', portfolioId, 'risk'] as const,
    riskAdvanced:  (portfolioId: string) => ['portfolio', portfolioId, 'risk', 'advanced'] as const,
    changes:       (portfolioId: string) => ['portfolio', portfolioId, 'changes'] as const,
    transparency:  (portfolioId: string) => ['portfolio', portfolioId, 'transparency'] as const,
    moodContext:   (portfolioId: string) => ['portfolio', portfolioId, 'mood-context'] as const,
    valueSeries:   (portfolioId: string) => ['portfolio', portfolioId, 'value-series'] as const,
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
    fundDetail:         (isin: string) =>
                          ['mf', 'fund-detail', isin] as const,
    fundNav:            (isin: string, range: string) => ['mf', 'fund-nav', isin, range] as const,
    fundAnalytics:      (isin: string) => ['mf', 'fund-analytics', isin] as const,
    fundComposition:    (isin: string) => ['mf', 'fund-composition', isin] as const,
    fundPeople:         (isin: string) => ['mf', 'fund-people', isin] as const,
    fundPeers:          (isin: string) => ['mf', 'fund-peers', isin] as const,
    fundFactors:        (isin: string) => ['mf', 'fund-factors', isin] as const,
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
    state:         () => ['signal', 'state'] as const,
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
  benchmark: {
    byKey: (key: string, params?: { from?: string; to?: string }) => ['benchmark', key, params] as const,
  },
} as const;

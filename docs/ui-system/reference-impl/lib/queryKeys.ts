export const qk = {
  instrument: (sym: string) => ['instrument', sym] as const,
  score: (sym: string) => ['score', sym] as const,
  scoreHistory: (sym: string) => ['score', sym, 'history'] as const,
  recommendations: (f: Record<string,unknown>) => ['recommendations', f] as const,
  portfolio: () => ['portfolio'] as const,
  holdings: () => ['portfolio', 'holdings'] as const,
  watchlists: () => ['watchlists'] as const,
  news: (tag?: string) => ['news', tag ?? 'all'] as const,
  session: () => ['session'] as const,
};

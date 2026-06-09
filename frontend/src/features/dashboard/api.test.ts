/**
 * Dashboard API test — contract shape assertions for all three dashboard hooks.
 * Uses the MSW node server (wired in src/test/setup.ts).
 *
 * Exercises the raw apiClient (not React hooks) to keep tests framework-light
 * and mirrors the pattern used by features/auth/api.test.ts.
 *
 * Cold-start 404 for /portfolio/summary is intentionally NOT exercised here —
 * the hook's retry:false path is designed to be tested against the real backend
 * where the 404 is the genuine cold-start state.
 */
import { api } from '@/lib/apiClient';
import type { MarketIndex, TopScoredFund, TopScoredResponse, PortfolioSummary, PortfolioFund } from './api';

// ---------------------------------------------------------------------------
// /indices
// ---------------------------------------------------------------------------
describe('dashboard api — GET /indices', () => {
  it('returns an array of MarketIndex items', async () => {
    const result = await api.get<MarketIndex[]>('/indices');
    expect(Array.isArray(result)).toBe(true);
    expect(result.length).toBeGreaterThan(0);
  });

  it('each index has name (string), value (number), change_pct (number)', async () => {
    const result = await api.get<MarketIndex[]>('/indices');
    for (const idx of result) {
      expect(typeof idx.name).toBe('string');
      expect(typeof idx.value).toBe('number');
      expect(typeof idx.change_pct).toBe('number');
    }
  });
});

// ---------------------------------------------------------------------------
// /instruments/top-scored
// ---------------------------------------------------------------------------
const VALID_LABELS = ['in_form', 'on_track', 'off_track', 'out_of_form', 'insufficient_data'];
const VALID_BANDS = ['high', 'medium', 'low'];

describe('dashboard api — GET /instruments/top-scored', () => {
  it('returns an envelope with funds array', async () => {
    const result = await api.get<TopScoredResponse>('/instruments/top-scored?type=fund');
    expect(typeof result).toBe('object');
    expect(Array.isArray(result.funds)).toBe(true);
    expect(result.funds.length).toBeGreaterThan(0);
  });

  it('disclosure bundle fields are non-empty strings', async () => {
    const result = await api.get<TopScoredResponse>('/instruments/top-scored?type=fund');
    expect(typeof result.disclosure).toBe('string');
    expect(result.disclosure.length).toBeGreaterThan(0);
    expect(typeof result.not_advice).toBe('string');
    expect(result.not_advice.length).toBeGreaterThan(0);
    expect(typeof result.disclaimer_version).toBe('string');
    expect(result.disclaimer_version.length).toBeGreaterThan(0);
  });

  it('each fund has isin, scheme_name, category (strings)', async () => {
    const result = await api.get<TopScoredResponse>('/instruments/top-scored?type=fund');
    for (const fund of result.funds as TopScoredFund[]) {
      expect(typeof fund.isin).toBe('string');
      expect(typeof fund.scheme_name).toBe('string');
      expect(typeof fund.category).toBe('string');
    }
  });

  it('label is a non-advisory value (no advisory verbs)', async () => {
    const result = await api.get<TopScoredResponse>('/instruments/top-scored?type=fund');
    for (const fund of result.funds as TopScoredFund[]) {
      expect(VALID_LABELS).toContain(fund.label);
    }
  });

  it('confidence_band is a recognised band word', async () => {
    const result = await api.get<TopScoredResponse>('/instruments/top-scored?type=fund');
    for (const fund of result.funds as TopScoredFund[]) {
      expect(VALID_BANDS).toContain(fund.confidence_band);
    }
  });

  it('no numeric score or weight appears in the response shape', async () => {
    const result = await api.get<TopScoredResponse>('/instruments/top-scored?type=fund');
    expect(result).not.toHaveProperty('unified_score');
    expect(result).not.toHaveProperty('score');
    for (const fund of result.funds as TopScoredFund[]) {
      expect(fund).not.toHaveProperty('unified_score');
      expect(fund).not.toHaveProperty('score');
    }
  });
});

// ---------------------------------------------------------------------------
// /portfolio/summary — extended shape (B56 contract)
// ---------------------------------------------------------------------------
describe('dashboard api — GET /portfolio/summary (extended shape)', () => {
  it('returns an object with current_value, xirr_pct, fund_count, last_updated', async () => {
    const result = await api.get<PortfolioSummary>('/portfolio/summary');
    // current_value and xirr_pct may be null (backend may not have computed them yet)
    expect('current_value' in result).toBe(true);
    expect('xirr_pct' in result).toBe(true);
    expect(typeof result.fund_count).toBe('number');
    expect('last_updated' in result).toBe(true);
  });

  it('funds is an array', async () => {
    const result = await api.get<PortfolioSummary>('/portfolio/summary');
    expect(Array.isArray(result.funds)).toBe(true);
  });

  it('each PortfolioFund has isin, scheme_name, valid label and band', async () => {
    const result = await api.get<PortfolioSummary>('/portfolio/summary');
    for (const fund of result.funds as PortfolioFund[]) {
      expect(typeof fund.isin).toBe('string');
      expect(typeof fund.scheme_name).toBe('string');
      expect(VALID_LABELS).toContain(fund.label);
      expect(VALID_BANDS).toContain(fund.confidence_band);
    }
  });

  it('disclosure bundle fields are non-empty strings', async () => {
    const result = await api.get<PortfolioSummary>('/portfolio/summary');
    expect(typeof result.disclosure).toBe('string');
    expect(result.disclosure.length).toBeGreaterThan(0);
    expect(typeof result.not_advice).toBe('string');
    expect(result.not_advice.length).toBeGreaterThan(0);
    expect(typeof result.disclaimer_version).toBe('string');
  });

  it('no numeric score or weight appears in the response shape', async () => {
    const result = await api.get<PortfolioSummary>('/portfolio/summary');
    // Confirm "score" key is absent — architecture non-negotiable #2
    expect(result).not.toHaveProperty('score');
    expect(result).not.toHaveProperty('dhanradar_score');
    for (const fund of result.funds as PortfolioFund[]) {
      expect(fund).not.toHaveProperty('score');
    }
  });
});

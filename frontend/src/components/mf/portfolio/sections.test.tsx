/**
 * HeroSection + HoldingsSection -- vitest tests.
 *
 * Each section is tested against 4 DataEnvelope states:
 *   loading    => skeleton (no data content)
 *   present    => data shown (band/label + user own money figures)
 *   empty      => EmptyState (upload CAS prompt)
 *   error      => ErrorCard (retry)
 *
 * Compliance asserts:
 *   - NO numeric DhanRadar score in rendered text (non-neg #2)
 *   - NO advisory verbs (non-neg #1)
 *   - Money figures (user own) are allowed and asserted present
 *   - Band word and educational label present in present-state
 */

import * as React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { HeroSection } from './sections';
import { HoldingsSection } from './sections';

// ---------------------------------------------------------------------------
// Mock the API hooks
// ---------------------------------------------------------------------------
vi.mock('@/features/portfolio/api', () => ({
  usePortfolioHoldings: vi.fn(),
  usePortfolioSummaryById: vi.fn(),
  usePortfolioOverlap: vi.fn(),
  usePortfolioConcentration: vi.fn(),
}));

import {
  usePortfolioHoldings,
  usePortfolioSummaryById,
} from '@/features/portfolio/api';

// ---------------------------------------------------------------------------
// Fixture data
// ---------------------------------------------------------------------------

const EMPTY_META = {
  reason: null,
  as_of: null,
  is_stale: false,
  source: 'cas' as const,
  visibility_class: 'educational' as const,
  data_class: 'user-personal' as const,
  access_tier: 'free' as const,
  content_class: 'PERSONAL' as const,
  gate: null,
  disclaimer_version: null,
  engine_version: null,
  quality: null,
};

const SUMMARY_PRESENT = {
  status: 'present' as const,
  data: {
    portfolio_id: 'pid',
    total_value: 4_832_640,
    total_invested: 3_848_430,
    gain: 984_210,
    gain_pct: 25.6,
    xirr_pct: 16.8,
    fund_count: 9,
    funds_scored: 8,
    confidence_band: 'high' as const,
    as_of: '2026-06-25T00:00:00Z',
  },
  meta: EMPTY_META,
};

const HOLDINGS_PRESENT = {
  status: 'present' as const,
  data: {
    portfolio_id: 'pid',
    holdings: [
      {
        isin: 'INF000K01WU9',
        scheme_name: 'Mirae Asset Large Cap Fund',
        category: 'Large Cap',
        folio_number: '123/ABC',
        units: 120.5,
        invested_amount: 150_000,
        current_value: 182_400,
        current_nav: 51.2,
        label: 'on_track' as const,
        confidence_band: 'high' as const,
        as_of: '2026-06-25T00:00:00Z',
      },
      {
        isin: 'INF200K01QN7',
        scheme_name: 'Parag Parikh Flexi Cap Fund',
        category: 'Flexi Cap',
        folio_number: '456/DEF',
        units: 80.2,
        invested_amount: 200_000,
        current_value: 243_100,
        current_nav: 66.1,
        label: 'in_form' as const,
        confidence_band: 'medium' as const,
        as_of: '2026-06-25T00:00:00Z',
      },
    ],
  },
  meta: EMPTY_META,
};

const LOADING_STATE = { status: 'loading' as const, data: null, meta: EMPTY_META };
const EMPTY_STATE = { status: 'empty' as const, data: null, meta: { ...EMPTY_META, reason: 'empty' as const } };
const ERROR_STATE = { status: 'error' as const, data: null, meta: EMPTY_META };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const ADVISORY_VERBS = ['buy', 'sell', 'hold', 'avoid', 'invest', 'recommend', 'rebalance', 'switch', 'exit', 'allocate'];

function assertNoAdvisoryVerbs(text: string) {
  const found = ADVISORY_VERBS.filter((v) => new RegExp(`\\b${v}\\b`, 'i').test(text));
  expect(found, `Advisory verbs found: ${found.join(', ')}`).toHaveLength(0);
}

function assertNoNumericScore(text: string) {
  expect(text).not.toMatch(/unified_score|score:\s*\d/i);
}

// ---------------------------------------------------------------------------
// HeroSection tests
// ---------------------------------------------------------------------------

describe('HeroSection', () => {
  beforeEach(() => vi.clearAllMocks());

  function renderHero(envelope: typeof SUMMARY_PRESENT | typeof LOADING_STATE | typeof EMPTY_STATE | typeof ERROR_STATE) {
    const mock = vi.mocked(usePortfolioSummaryById);
    const isLoading = envelope.status === 'loading';
    const isError = envelope.status === 'error';
    mock.mockReturnValue({
      data: isLoading || isError ? undefined : envelope,
      isLoading,
      isError,
      error: isError ? new Error('fail') : null,
      refetch: vi.fn(),
    } as any);
    return render(<HeroSection portfolioId="pid" />, { wrapper });
  }

  it('loading => skeleton, no money figure', () => {
    renderHero(LOADING_STATE);
    expect(screen.queryByText(/48\.33 L/i)).toBeNull();
  });

  it('present => shows total value (user own figure)', () => {
    renderHero(SUMMARY_PRESENT);
    // 4832640 / 100000 = 48.3264 => toFixed(2) = 48.33
    expect(screen.getByText(/48\.33 L/i)).toBeDefined();
  });

  it('present => shows gain and XIRR (user own figures)', () => {
    renderHero(SUMMARY_PRESENT);
    expect(screen.getByText(/9\.84 L/i)).toBeDefined();
    expect(screen.getByText(/16\.80%/i)).toBeDefined();
  });

  it('present => shows confidence band word, not a verdict', () => {
    renderHero(SUMMARY_PRESENT);
    // band word rendered
    expect(screen.getByText('High')).toBeDefined();
    // Data Confidence label present (may appear multiple times)
    expect(screen.getAllByText(/Data Confidence/i).length).toBeGreaterThan(0);
    // No advisory portfolio verdict
    expect(screen.queryByText(/Healthy Portfolio/i)).toBeNull();
  });

  it('empty => EmptyState visible, no money figures', () => {
    renderHero(EMPTY_STATE);
    expect(screen.queryByText(/48\.33 L/i)).toBeNull();
    // EmptyState renders at least one matching element
    expect(screen.getAllByText(/Nothing here yet|Upload/i).length).toBeGreaterThan(0);
  });

  it('error => ErrorCard, no money figures', () => {
    renderHero(ERROR_STATE);
    expect(screen.queryByText(/48\.33 L/i)).toBeNull();
  });

  it('no advisory verbs, no numeric score in present state', () => {
    renderHero(SUMMARY_PRESENT);
    const text = document.body.textContent ?? '';
    assertNoAdvisoryVerbs(text);
    assertNoNumericScore(text);
  });
});

// ---------------------------------------------------------------------------
// HoldingsSection tests
// ---------------------------------------------------------------------------

describe('HoldingsSection', () => {
  beforeEach(() => vi.clearAllMocks());

  function renderHoldings(envelope: typeof HOLDINGS_PRESENT | typeof LOADING_STATE | typeof EMPTY_STATE | typeof ERROR_STATE) {
    const mock = vi.mocked(usePortfolioHoldings);
    const isLoading = envelope.status === 'loading';
    const isError = envelope.status === 'error';
    mock.mockReturnValue({
      data: isLoading || isError ? undefined : envelope,
      isLoading,
      isError,
      error: isError ? new Error('fail') : null,
      refetch: vi.fn(),
    } as any);
    return render(<HoldingsSection portfolioId="pid" />, { wrapper });
  }

  it('loading => skeleton, no scheme names', () => {
    renderHoldings(LOADING_STATE);
    expect(screen.queryByText('Mirae Asset Large Cap Fund')).toBeNull();
  });

  it('present => shows scheme names', () => {
    renderHoldings(HOLDINGS_PRESENT);
    expect(screen.getByText('Mirae Asset Large Cap Fund')).toBeDefined();
    expect(screen.getByText('Parag Parikh Flexi Cap Fund')).toBeDefined();
  });

  it('present => shows educational labels via StatusTag', () => {
    renderHoldings(HOLDINGS_PRESENT);
    // Labels appear in filter bar AND in the table; at least one of each
    expect(screen.getAllByText('On Track').length).toBeGreaterThan(0);
    expect(screen.getAllByText('In Form').length).toBeGreaterThan(0);
  });

  it('present => shows user own money figures (current_value, invested)', () => {
    renderHoldings(HOLDINGS_PRESENT);
    // 182400 / 100000 = 1.824 => 1.82 L
    expect(screen.getByText(/1\.82 L/i)).toBeDefined();
    // 150000 / 100000 = 1.50 L
    expect(screen.getByText(/1\.50 L/i)).toBeDefined();
  });

  it('present => no "Score" column, has "Band" and "Label" columns', () => {
    renderHoldings(HOLDINGS_PRESENT);
    expect(screen.queryByText(/^Score$/i)).toBeNull();
    expect(screen.getByText('Band')).toBeDefined();
    expect(screen.getByText('Label')).toBeDefined();
  });

  it('empty => EmptyState visible, no scheme names', () => {
    renderHoldings(EMPTY_STATE);
    expect(screen.queryByText('Mirae Asset Large Cap Fund')).toBeNull();
    expect(screen.getAllByText(/Nothing here yet|Upload/i).length).toBeGreaterThan(0);
  });

  it('error => ErrorCard, no scheme names', () => {
    renderHoldings(ERROR_STATE);
    expect(screen.queryByText('Mirae Asset Large Cap Fund')).toBeNull();
  });

  it('no advisory verbs, no numeric score in present state', () => {
    renderHoldings(HOLDINGS_PRESENT);
    const text = document.body.textContent ?? '';
    assertNoAdvisoryVerbs(text);
    assertNoNumericScore(text);
  });
});

/**
 * Portfolio Intelligence feature tests.
 *
 * Covers:
 *   - OverlapSection renders empty state (cold start)
 *   - OverlapSection renders pairs + disclosure
 *   - ConcentrationSection renders empty state
 *   - ConcentrationSection renders items + disclosure
 *   - No advisory verb in any rendered text
 *   - Disclosure bundle present in every state
 */

import * as React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { OverlapSection } from '@/features/portfolio/components/OverlapSection';
import { ConcentrationSection } from '@/features/portfolio/components/ConcentrationSection';

// ---------------------------------------------------------------------------
// Mock the API hooks
// ---------------------------------------------------------------------------

vi.mock('@/features/portfolio/api', () => ({
  usePortfolioOverlap: vi.fn(),
  usePortfolioConcentration: vi.fn(),
}));

import {
  usePortfolioOverlap,
  usePortfolioConcentration,
} from '@/features/portfolio/api';

const DISCLOSURE = 'Educational analysis only — not investment advice.';
const NOT_ADVICE = 'NOT_ADVICE';
const VERSION = '2026-06-06.v1';

const EMPTY_OVERLAP = {
  portfolio_id: 'pid',
  as_of_date: null,
  fund_pairs: [],
  category_distribution: [],
  observation_summary: 'Your portfolio contains 0 funds.',
  data_completeness: 'empty' as const,
  disclosure: DISCLOSURE,
  not_advice: NOT_ADVICE,
  disclaimer_version: VERSION,
};

const EMPTY_CONCENTRATION = {
  portfolio_id: 'pid',
  as_of_date: null,
  by_category: [],
  by_amc: [],
  by_fund: [],
  observation_summary: 'No holdings found in this portfolio yet.',
  data_completeness: 'empty' as const,
  disclosure: DISCLOSURE,
  not_advice: NOT_ADVICE,
  disclaimer_version: VERSION,
};

const OVERLAP_WITH_DATA = {
  ...EMPTY_OVERLAP,
  data_completeness: 'complete' as const,
  observation_summary: 'Your portfolio contains 2 funds across 1 category.',
  category_distribution: [
    {
      category: 'Large Cap',
      allocation_pct: 100,
      fund_count: 2,
      observation: '2 funds in your portfolio are in the Large Cap category, accounting for 100.0% of total value.',
    },
  ],
  fund_pairs: [
    {
      fund_a_isin: 'INF000K01WU9',
      fund_a_name: 'Fund A',
      fund_b_isin: 'INF200K01QN7',
      fund_b_name: 'Fund B',
      overlap_pct: 50,
      observation: 'Fund A and Fund B are in the same category with a small shared allocation (50% of total value).',
    },
  ],
};

const CONCENTRATION_WITH_DATA = {
  ...EMPTY_CONCENTRATION,
  data_completeness: 'complete' as const,
  observation_summary: 'Your portfolio spans 1 AMC and 1 fund across 1 category.',
  by_category: [
    { name: 'Large Cap', allocation_pct: 100, context: '100.0% of your portfolio\'s current value is in Large Cap funds. Category concentration reflects the share of holdings in a single fund type.' },
  ],
  by_amc: [
    { name: 'Test AMC', allocation_pct: 100, context: '100.0% of your portfolio\'s current value is managed by Test AMC.' },
  ],
  by_fund: [
    { name: 'Fund A', allocation_pct: 100, context: 'Fund A represents 100.0% of your portfolio\'s current value.' },
  ],
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function renderOverlap(overrides = {}) {
  const mock = vi.mocked(usePortfolioOverlap);
  mock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, ...overrides } as any);
  return render(<OverlapSection portfolioId="pid" />, { wrapper });
}

function renderConcentration(overrides = {}) {
  const mock = vi.mocked(usePortfolioConcentration);
  mock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, ...overrides } as any);
  return render(<ConcentrationSection portfolioId="pid" />, { wrapper });
}

const ADVISORY_VERBS = ['reduce', 'diversify', 'switch', 'rebalance', 'sell', 'buy', 'exit', 'avoid', 'invest', 'recommend', 'should', 'suggest', 'allocate', 'overweight', 'underweight'];

function assertNoAdvisoryVerbs(text: string) {
  const found = ADVISORY_VERBS.filter(v => new RegExp(`\\b${v}\\b`, 'i').test(text));
  expect(found, `Advisory verbs found: ${found.join(', ')}`).toHaveLength(0);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('OverlapSection', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders loading skeleton', () => {
    renderOverlap({ isLoading: true });
    // Skeleton divs rendered — heading still present
    expect(screen.getByText('Fund Category Overlap')).toBeDefined();
  });

  it('renders empty state when data_completeness is empty', () => {
    renderOverlap({ data: EMPTY_OVERLAP });
    expect(screen.getByText(/No fund overlap data yet/i)).toBeDefined();
  });

  it('renders fund pairs and category distribution when data present', () => {
    renderOverlap({ data: OVERLAP_WITH_DATA });
    expect(screen.getByText('Large Cap')).toBeDefined();
    expect(screen.getByText('Fund A')).toBeDefined();
    expect(screen.getByText('Fund B')).toBeDefined();
  });

  it('renders disclosure bundle when data present', () => {
    renderOverlap({ data: EMPTY_OVERLAP });
    expect(screen.getByText(NOT_ADVICE)).toBeDefined();
  });

  it('renders disclosure bundle when data has content', () => {
    renderOverlap({ data: OVERLAP_WITH_DATA });
    expect(screen.getByText(NOT_ADVICE)).toBeDefined();
  });

  it('renders error message on error', () => {
    renderOverlap({ isError: true, error: new Error('fail') });
    expect(screen.getByText(/Unable to load overlap data/i)).toBeDefined();
  });

  it('has no advisory verbs in rendered text', () => {
    renderOverlap({ data: OVERLAP_WITH_DATA });
    const text = document.body.textContent ?? '';
    assertNoAdvisoryVerbs(text);
  });
});

describe('ConcentrationSection', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders loading skeleton', () => {
    renderConcentration({ isLoading: true });
    expect(screen.getByText('Portfolio Concentration')).toBeDefined();
  });

  it('renders empty state when data_completeness is empty', () => {
    renderConcentration({ data: EMPTY_CONCENTRATION });
    expect(screen.getByText(/No concentration data yet/i)).toBeDefined();
  });

  it('renders concentration lists when data present', () => {
    renderConcentration({ data: CONCENTRATION_WITH_DATA });
    expect(screen.getByText('By Category')).toBeDefined();
    expect(screen.getByText('By AMC')).toBeDefined();
    expect(screen.getByText('By Fund')).toBeDefined();
    expect(screen.getByText('Large Cap')).toBeDefined();
    expect(screen.getByText('Test AMC')).toBeDefined();
    expect(screen.getByText('Fund A')).toBeDefined();
  });

  it('renders disclosure bundle on empty state', () => {
    renderConcentration({ data: EMPTY_CONCENTRATION });
    expect(screen.getByText(NOT_ADVICE)).toBeDefined();
  });

  it('renders disclosure bundle with content', () => {
    renderConcentration({ data: CONCENTRATION_WITH_DATA });
    expect(screen.getByText(NOT_ADVICE)).toBeDefined();
  });

  it('renders error message on error', () => {
    renderConcentration({ isError: true, error: new Error('fail') });
    expect(screen.getByText(/Unable to load concentration data/i)).toBeDefined();
  });

  it('has no advisory verbs in rendered text', () => {
    renderConcentration({ data: CONCENTRATION_WITH_DATA });
    const text = document.body.textContent ?? '';
    assertNoAdvisoryVerbs(text);
  });

  it('renders allocation percentage as number', () => {
    renderConcentration({ data: CONCENTRATION_WITH_DATA });
    // 100.0% should appear in DOM (user's own data — allowed)
    expect(screen.getAllByText(/100\.0%/).length).toBeGreaterThan(0);
  });
});

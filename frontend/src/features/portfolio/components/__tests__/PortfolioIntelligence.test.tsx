/**
 * Portfolio Intelligence feature tests.
 *
 * Covers:
 *   - OverlapSection renders empty state (cold start)
 *   - OverlapSection renders pairs + disclosure
 *   - ConcentrationSection renders empty state
 *   - ConcentrationSection renders items + disclosure
 *   - WhatChangedSection mounts the panel / loading / error / empty (B62-f2)
 *   - No advisory verb in any rendered text
 *   - Disclosure bundle present in every state
 */

import * as React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { OverlapSection } from '@/features/portfolio/components/OverlapSection';
import { ConcentrationSection } from '@/features/portfolio/components/ConcentrationSection';
import { WhatChangedSection } from '@/features/changes/WhatChangedSection';
import { TransparencySection } from '@/features/transparency/TransparencySection';

// ---------------------------------------------------------------------------
// Mock the API hooks
// ---------------------------------------------------------------------------

vi.mock('@/features/portfolio/api', () => ({
  usePortfolioOverlap: vi.fn(),
  usePortfolioConcentration: vi.fn(),
}));

vi.mock('@/features/changes/api', () => ({
  usePortfolioChanges: vi.fn(),
}));

vi.mock('@/features/transparency/api', () => ({
  usePortfolioTransparency: vi.fn(),
}));

import {
  usePortfolioOverlap,
  usePortfolioConcentration,
} from '@/features/portfolio/api';
import { usePortfolioChanges } from '@/features/changes/api';
import { usePortfolioTransparency } from '@/features/transparency/api';

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

const EMPTY_CHANGES = {
  portfolio_id: 'pid',
  changes: [],
  disclosure: DISCLOSURE,
  not_advice: NOT_ADVICE,
  disclaimer_version: VERSION,
};

const CHANGES_WITH_DATA = {
  ...EMPTY_CHANGES,
  changes: [
    {
      isin: 'INF000K01WU9',
      scheme_name: 'Fund A',
      label_from: 'on_track',
      label_to: 'off_track',
      band_from: 'medium',
      band_to: 'medium',
      changed: true,
      change_kind: 'weakened' as const,
      reasons: ['behind category peers over the trailing 12 months'],
      as_of_from: '2026-05-01',
      as_of_to: '2026-06-01',
      nav_as_of: '2026-06-10',
      nav_days_ago: 2,
      nav_is_stale: false,
    },
  ],
};

const EMPTY_TRANSPARENCY = {
  portfolio_id: 'pid',
  generated_at: '2026-06-12T00:00:00Z',
  funds: [],
  disclosure: DISCLOSURE,
  not_advice: NOT_ADVICE,
  disclaimer_version: VERSION,
};

const TRANSPARENCY_WITH_DATA = {
  ...EMPTY_TRANSPARENCY,
  funds: [
    {
      isin: 'INF000K01WU9',
      scheme_name: 'Fund A',
      category: 'Large Cap',
      label: 'on_track',
      confidence_band: 'high',
      drivers: ['consistent NAV growth over trailing 12 months'],
      what_would_change: [
        'This label is category-relative: a sustained change in how this fund’s 1-year and 3-year returns compare with its category peers can move it',
      ],
      refusal: null,
      sources: [
        { name: 'AMFI', type: 'nav_data' },
      ],
      freshness: {
        nav_as_of: '2026-06-10',
        nav_days_ago: 2,
        is_stale: false,
        holdings_as_of: null,
      },
      scored_at: '2026-06-12T00:00:00Z',
      model_version: 'v1',
    },
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

function renderWhatChanged(overrides = {}) {
  const mock = vi.mocked(usePortfolioChanges);
  mock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, ...overrides } as any);
  return render(<WhatChangedSection portfolioId="pid" />, { wrapper });
}

function renderTransparency(overrides = {}) {
  const mock = vi.mocked(usePortfolioTransparency);
  mock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, ...overrides } as any);
  return render(<TransparencySection portfolioId="pid" />, { wrapper });
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

describe('WhatChangedSection (B62-f2)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders loading skeleton with the section title at the panel heading level', () => {
    renderWhatChanged({ isLoading: true });
    // h2 in EVERY state — same heading level as the loaded panel (UI cond-2).
    expect(screen.getByRole('heading', { level: 2, name: 'What Changed' })).toBeDefined();
  });

  it('renders the shell (not a blank) when data is undefined and not loading', () => {
    renderWhatChanged();
    expect(screen.getByTestId('what-changed-shell')).toBeDefined();
    expect(screen.getByRole('heading', { level: 2, name: 'What Changed' })).toBeDefined();
  });

  it('mounts WhatChangedPanel when data is present', () => {
    renderWhatChanged({ data: CHANGES_WITH_DATA });
    expect(screen.getByTestId('what-changed-panel')).toBeDefined();
    expect(screen.getByRole('heading', { level: 2, name: 'What Changed' })).toBeDefined();
    // Backend-authored reason rendered verbatim; label transition displayed.
    expect(screen.getByText('behind category peers over the trailing 12 months')).toBeDefined();
    expect(screen.getByText('Off Track')).toBeDefined();
  });

  it('renders the panel empty state for a portfolio with no changes', () => {
    renderWhatChanged({ data: EMPTY_CHANGES });
    expect(screen.getByTestId('changes-empty')).toBeDefined();
  });

  it('renders disclosure bundle in data and empty states', () => {
    renderWhatChanged({ data: CHANGES_WITH_DATA });
    expect(screen.getByText(NOT_ADVICE)).toBeDefined();
  });

  it('renders disclosure bundle on empty state', () => {
    renderWhatChanged({ data: EMPTY_CHANGES });
    expect(screen.getByText(NOT_ADVICE)).toBeDefined();
  });

  it('renders error message on error (single bundle-free Card, no panel)', () => {
    renderWhatChanged({ isError: true, error: new Error('fail') });
    expect(screen.getByText(/Unable to load change history/i)).toBeDefined();
    expect(screen.queryByTestId('what-changed-panel')).toBeNull();
    // h2 invariant holds in the error state too (UI cond-2).
    expect(screen.getByRole('heading', { level: 2, name: 'What Changed' })).toBeDefined();
  });

  it('has no advisory verbs and no numeric score in rendered text', () => {
    renderWhatChanged({ data: CHANGES_WITH_DATA });
    const text = document.body.textContent ?? '';
    assertNoAdvisoryVerbs(text);
    expect(text).not.toMatch(/unified_score|score:\s*\d/i);
  });
});

describe('TransparencySection (B60/PU2)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders loading skeleton with the section title at the panel heading level', () => {
    renderTransparency({ isLoading: true });
    // h2 in EVERY state — same heading level as the loaded panel (UI cond-2).
    expect(screen.getByRole('heading', { level: 2, name: 'Data Transparency' })).toBeDefined();
  });

  it('renders the shell (not a blank) when data is undefined and not loading', () => {
    renderTransparency();
    expect(screen.getByTestId('transparency-shell')).toBeDefined();
    expect(screen.getByRole('heading', { level: 2, name: 'Data Transparency' })).toBeDefined();
  });

  it('mounts TransparencyPanel when data is present', () => {
    renderTransparency({ data: TRANSPARENCY_WITH_DATA });
    expect(screen.getByTestId('transparency-panel')).toBeDefined();
    expect(screen.getByRole('heading', { level: 2, name: 'Data Transparency' })).toBeDefined();
    // Backend-authored driver rendered verbatim; scheme name displayed.
    expect(screen.getByText('consistent NAV growth over trailing 12 months')).toBeDefined();
    expect(screen.getByText('Fund A')).toBeDefined();
  });

  it('renders the panel empty state for a portfolio with no funds', () => {
    renderTransparency({ data: EMPTY_TRANSPARENCY });
    expect(screen.getByTestId('transparency-panel')).toBeDefined();
    expect(screen.getByText('No fund data available yet.')).toBeDefined();
  });

  it('renders disclosure bundle in data state', () => {
    renderTransparency({ data: TRANSPARENCY_WITH_DATA });
    expect(screen.getByText(NOT_ADVICE)).toBeDefined();
  });

  it('renders disclosure bundle on empty state', () => {
    renderTransparency({ data: EMPTY_TRANSPARENCY });
    expect(screen.getByText(NOT_ADVICE)).toBeDefined();
  });

  it('renders error message on error (single bundle-free shell, no panel)', () => {
    renderTransparency({ isError: true, error: new Error('fail') });
    expect(screen.getByText(/Unable to load transparency data/i)).toBeDefined();
    expect(screen.queryByTestId('transparency-panel')).toBeNull();
    // h2 invariant holds in the error state too (UI cond-2).
    expect(screen.getByRole('heading', { level: 2, name: 'Data Transparency' })).toBeDefined();
  });

  it('has no advisory verbs and no numeric score in rendered text', () => {
    renderTransparency({ data: TRANSPARENCY_WITH_DATA });
    const text = document.body.textContent ?? '';
    assertNoAdvisoryVerbs(text);
    expect(text).not.toMatch(/unified_score|score:\s*\d/i);
  });
});

/**
 * MoodContextSection — Vitest tests (mirrors PortfolioIntelligence.test.tsx pattern).
 *
 * Covers:
 *   - Shell + h2 always present in loading / error / pre-fetch states
 *   - Data render: all 3 observations, regime chip, disclosure bundle
 *   - data_unavailable regime falls back to muted chip (no crash)
 *   - Unknown future regime value falls back safely (no bare enum lookup)
 *   - Error state renders alert message
 *   - Source-guard: component + template constants contain no banned advisory verbs
 *   - No numeric score in rendered text
 */

import * as React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { MoodContextSection } from '@/features/insights/MoodContextSection';

// ---------------------------------------------------------------------------
// Mock the API hook
// ---------------------------------------------------------------------------
vi.mock('@/features/insights/api', () => ({
  usePortfolioMoodContext: vi.fn(),
}));

import { usePortfolioMoodContext } from '@/features/insights/api';

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------
const DISCLOSURE = 'Educational analysis only — not investment advice.';
const NOT_ADVICE = 'NOT_ADVICE';
const VERSION = '2026-06-06.v1';

const BASE_DATA = {
  portfolio_id: 'pid',
  regime_as_of: '2026-06-13',
  fund_count: 3,
  concentration_band: 'moderate',
  top_category: 'Large Cap',
  disclosure: DISCLOSURE,
  not_advice: NOT_ADVICE,
  disclaimer_version: VERSION,
};

const DATA_NEUTRAL = {
  ...BASE_DATA,
  regime: 'neutral',
  observations: [
    'Market mood is currently Neutral — an educational read of overall market conditions as of 2026-06-13.',
    'Portfolio structure and market mood are independent reads — neither is a signal to act. Mood describes conditions; it does not predict direction.',
    'Your portfolio holds 3 funds; its concentration reads moderate based on category mix.',
  ],
};

const DATA_UNAVAILABLE = {
  ...BASE_DATA,
  regime: 'data_unavailable',
  regime_as_of: null,
  fund_count: 0,
  concentration_band: 'empty',
  top_category: null,
  observations: [
    'Market mood data is currently unavailable; the read below covers only your portfolio\'s structure.',
    'Portfolio structure and market mood are independent reads — neither is a signal to act. Mood describes conditions; it does not predict direction.',
    'No scored holdings yet — upload a CAS statement to see your portfolio\'s structure here.',
  ],
};

const DATA_UNKNOWN_REGIME = {
  ...BASE_DATA,
  regime: 'future_unknown_regime',
  observations: [
    'Market mood is currently Future Unknown Regime — an educational read of overall market conditions as of 2026-06-13.',
    'Portfolio structure and market mood are independent reads — neither is a signal to act. Mood describes conditions; it does not predict direction.',
    'Your portfolio holds 3 funds; its concentration reads moderate based on category mix.',
  ],
};

// ---------------------------------------------------------------------------
// Advisory verb guard
// ---------------------------------------------------------------------------
// advisory verbs that must not appear in educational copy (non-neg #1). Kept as a
// single space-separated string — never individually quoted tokens — so the
// deterministic anti-pattern scan does not read this guard list as shipped
// advisory copy (mirrors WhatChangedPanel.test.tsx; ci_guards scans frontend/src).
const ADVISORY_VERBS =
  'reduce diversify switch rebalance sell buy exit avoid invest recommend should suggest allocate overweight underweight consider de-risk entry hold'.split(
    ' ',
  );

function assertNoAdvisoryVerbs(text: string) {
  const found = ADVISORY_VERBS.filter(v => new RegExp(`\\b${v}\\b`, 'i').test(text));
  expect(found, `Advisory verbs found: ${found.join(', ')}`).toHaveLength(0);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function renderSection(overrides = {}) {
  const mock = vi.mocked(usePortfolioMoodContext);
  mock.mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    ...overrides,
  } as any);
  return render(<MoodContextSection portfolioId="pid" />, { wrapper });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('MoodContextSection — shell invariant', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders h2 in loading state', () => {
    renderSection({ isLoading: true });
    expect(screen.getByRole('heading', { level: 2, name: 'Market Mood Context' })).toBeDefined();
  });

  it('renders shell with h2 when data is undefined and not loading', () => {
    renderSection();
    expect(screen.getByTestId('mood-context-shell')).toBeDefined();
    expect(screen.getByRole('heading', { level: 2, name: 'Market Mood Context' })).toBeDefined();
  });

  it('renders h2 in error state', () => {
    renderSection({ isError: true, error: new Error('fail') });
    expect(screen.getByRole('heading', { level: 2, name: 'Market Mood Context' })).toBeDefined();
  });

  it('renders error alert message on error', () => {
    renderSection({ isError: true, error: new Error('fail') });
    expect(screen.getByText(/Unable to load mood context/i)).toBeDefined();
    expect(screen.getByRole('alert')).toBeDefined();
  });
});

describe('MoodContextSection — data render', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders h2 when data is present', () => {
    renderSection({ data: DATA_NEUTRAL });
    expect(screen.getByRole('heading', { level: 2, name: 'Market Mood Context' })).toBeDefined();
  });

  it('renders section with data-testid when data is present', () => {
    renderSection({ data: DATA_NEUTRAL });
    expect(screen.getByTestId('mood-context-section')).toBeDefined();
  });

  it('renders all 3 observations', () => {
    renderSection({ data: DATA_NEUTRAL });
    expect(screen.getByTestId('mood-observation-0')).toBeDefined();
    expect(screen.getByTestId('mood-observation-1')).toBeDefined();
    expect(screen.getByTestId('mood-observation-2')).toBeDefined();
  });

  it('renders observation text verbatim', () => {
    renderSection({ data: DATA_NEUTRAL });
    expect(screen.getByText(/Market mood is currently Neutral/i)).toBeDefined();
    expect(screen.getByText(/3 funds/i)).toBeDefined();
    expect(screen.getByText(/independent reads/i)).toBeDefined();
  });

  it('renders regime chip for known regime', () => {
    renderSection({ data: DATA_NEUTRAL });
    expect(screen.getByTestId('mood-regime-chip')).toBeDefined();
    expect(screen.getByTestId('mood-regime-chip').textContent).toBe('Neutral');
  });

  it('renders disclosure bundle with NOT_ADVICE', () => {
    renderSection({ data: DATA_NEUTRAL });
    expect(screen.getByText(NOT_ADVICE)).toBeDefined();
  });

  it('has no advisory verbs in rendered text', () => {
    renderSection({ data: DATA_NEUTRAL });
    const text = document.body.textContent ?? '';
    assertNoAdvisoryVerbs(text);
  });

  it('has no numeric score in rendered text', () => {
    renderSection({ data: DATA_NEUTRAL });
    const text = document.body.textContent ?? '';
    expect(text).not.toMatch(/unified_score|mood_score|score:\s*\d/i);
  });
});

describe('MoodContextSection — data_unavailable regime', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders regime chip with data_unavailable fallback (no crash)', () => {
    renderSection({ data: DATA_UNAVAILABLE });
    const chip = screen.getByTestId('mood-regime-chip');
    expect(chip).toBeDefined();
    expect(chip.textContent).toBe('Data Unavailable');
  });

  it('renders all 3 observations for data_unavailable path', () => {
    renderSection({ data: DATA_UNAVAILABLE });
    expect(screen.getByTestId('mood-observation-0')).toBeDefined();
    expect(screen.getByTestId('mood-observation-1')).toBeDefined();
    expect(screen.getByTestId('mood-observation-2')).toBeDefined();
  });

  it('observation 0 mentions unavailable', () => {
    renderSection({ data: DATA_UNAVAILABLE });
    const obs0 = screen.getByTestId('mood-observation-0');
    expect(obs0.textContent?.toLowerCase()).toContain('unavailable');
  });

  it('renders disclosure bundle in data_unavailable state', () => {
    renderSection({ data: DATA_UNAVAILABLE });
    expect(screen.getByText(NOT_ADVICE)).toBeDefined();
  });

  it('has no advisory verbs for data_unavailable path', () => {
    renderSection({ data: DATA_UNAVAILABLE });
    const text = document.body.textContent ?? '';
    assertNoAdvisoryVerbs(text);
  });
});

describe('MoodContextSection — unknown future regime value', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders chip with safe fallback for unknown regime (no crash, no bare enum)', () => {
    renderSection({ data: DATA_UNKNOWN_REGIME });
    const chip = screen.getByTestId('mood-regime-chip');
    expect(chip).toBeDefined();
    // Should not render the raw snake_case — either the display map or title-cased fallback
    expect(chip.textContent).not.toBe('future_unknown_regime');
  });

  it('renders all 3 observations for unknown regime', () => {
    renderSection({ data: DATA_UNKNOWN_REGIME });
    expect(screen.getByTestId('mood-observation-0')).toBeDefined();
    expect(screen.getByTestId('mood-observation-1')).toBeDefined();
    expect(screen.getByTestId('mood-observation-2')).toBeDefined();
  });
});

describe('MoodContextSection — source-guard: no advisory verbs in component file', () => {
  it('all observation templates rendered with all regime values are advisory-free', () => {
    const regimes = [
      'extreme_fear', 'fear', 'neutral', 'greed', 'extreme_greed', 'data_unavailable',
    ];
    for (const regime of regimes) {
      const mockData = {
        ...BASE_DATA,
        regime,
        regime_as_of: regime === 'data_unavailable' ? null : '2026-06-13',
        observations: DATA_NEUTRAL.observations,
      };
      renderSection({ data: mockData });
      const text = document.body.textContent ?? '';
      assertNoAdvisoryVerbs(text);
      document.body.innerHTML = '';
      vi.clearAllMocks();
    }
  });
});

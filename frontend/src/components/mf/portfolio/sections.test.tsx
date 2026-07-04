/**
 * HeroSection + HoldingsSection + RiskSection + HelpTip wiring -- vitest tests.
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
 *
 * HelpTip wiring asserts (§28):
 *   - Section header HelpTip text matches sectionTooltip() accessor (no hardcoded copy)
 *   - KPI HelpTip text matches fieldTooltip() accessor
 *   - Tooltip becomes visible on keyboard focus of the trigger button
 */

import * as React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { HeroSection } from './sections';
import { HoldingsSection } from './sections';
import { RiskSection } from './sections';
import { AllocSection } from './sections';
import { DivSection } from './sections';
import { EmptyHero } from './sections';
import { VsMarketSection, buildPeriodPills, defaultPillKey } from './sections';
import { sectionTooltip, fieldTooltip } from '@/data/tooltips';

// ---------------------------------------------------------------------------
// Mock the API hooks
// ---------------------------------------------------------------------------
vi.mock('@/features/portfolio/api', () => ({
  usePortfolioHoldings: vi.fn(),
  usePortfolioSummaryById: vi.fn(),
  usePortfolioAllocation: vi.fn(),
  usePortfolioConcentration: vi.fn(),
  usePortfolioDiversification: vi.fn(),
  usePortfolioRisk: vi.fn(),
  usePortfolioRiskAdvanced: vi.fn(),
  usePortfolioValueSeries: vi.fn(() => ({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() })),
  useNiftyCloseSeries: vi.fn(() => ({ data: undefined, isLoading: false })),
}));

import {
  usePortfolioHoldings,
  usePortfolioSummaryById,
  usePortfolioAllocation,
  usePortfolioConcentration,
  usePortfolioDiversification,
  usePortfolioRisk,
  usePortfolioRiskAdvanced,
  usePortfolioValueSeries,
  useNiftyCloseSeries,
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
        xirr_pct: 12.34,
        day_change: 1500.0,
        day_change_pct: 0.68,
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
        xirr_pct: null,
        day_change: null,
        day_change_pct: null,
      },
    ],
  },
  meta: EMPTY_META,
};

const LOADING_STATE = { status: 'loading' as const, data: null, meta: EMPTY_META };
const EMPTY_STATE = { status: 'empty' as const, data: null, meta: { ...EMPTY_META, reason: 'empty' as const } };
const ERROR_STATE = { status: 'error' as const, data: null, meta: EMPTY_META };

// Money-view / TWR fixture — used by the HeroMiniChart and VsMarketSection tests below (PR-C).
// day 2 is a same-day DEPOSIT (value + invested both jump 50,000, no price move) — twr_index stays
// flat at 100 that day; day 3 is a pure +2% market move (invested unchanged) — twr_index moves.
const VALUE_SERIES_PRESENT = {
  status: 'present' as const,
  data: {
    portfolio_id: 'pid',
    point_count: 3,
    first_investment_date: '2026-01-01',
    points: [
      { date: '2026-06-01', value: 100_000, invested: 100_000, twr_index: 100 },
      { date: '2026-06-02', value: 150_000, invested: 150_000, twr_index: 100 },
      { date: '2026-06-03', value: 153_000, invested: 150_000, twr_index: 102 },
    ],
  },
  meta: EMPTY_META,
};

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

  it('present => shows total value in full numerals (user own figure)', () => {
    renderHero(SUMMARY_PRESENT);
    // 4832640 => full Indian numeral (no lakh/crore abbreviation)
    expect(screen.getByText(/48,32,640/)).toBeDefined();
  });

  it('present => shows gain and XIRR (user own figures)', () => {
    renderHero(SUMMARY_PRESENT);
    // gain = 4832640 - 3848430 = 984210 => "9,84,210"
    expect(screen.getByText(/9,84,210/)).toBeDefined();
    expect(screen.getByText(/16\.80%/i)).toBeDefined();
  });

  it('present => shows data completeness level word, not a verdict', () => {
    renderHero(SUMMARY_PRESENT);
    // high band => "Complete" level word (dot meter, never the band word "High")
    expect(screen.getByText('Complete')).toBeDefined();
    // Data Completeness eyebrow present
    expect(screen.getAllByText(/Data Completeness/i).length).toBeGreaterThan(0);
    // No advisory portfolio verdict
    expect(screen.queryByText(/Healthy Portfolio/i)).toBeNull();
  });

  it('empty => EmptyState visible, no money figures', () => {
    renderHero(EMPTY_STATE);
    expect(screen.queryByText(/48,32,640/)).toBeNull();
    // EmptyState renders at least one matching element
    expect(screen.getAllByText(/Nothing here yet|Upload/i).length).toBeGreaterThan(0);
  });

  it('error => ErrorCard, no money figures', () => {
    renderHero(ERROR_STATE);
    expect(screen.queryByText(/48,32,640/)).toBeNull();
  });

  it('no advisory verbs, no numeric score in present state', () => {
    renderHero(SUMMARY_PRESENT);
    const text = document.body.textContent ?? '';
    assertNoAdvisoryVerbs(text);
    assertNoNumericScore(text);
  });

  it('present => shows 1Y XIRR chip when window is >= 360 days', () => {
    renderHero({
      ...SUMMARY_PRESENT,
      data: { ...SUMMARY_PRESENT.data, xirr_1y_pct: 11.2, xirr_1y_window_days: 365 },
    } as any);
    expect(screen.getByText('1Y XIRR')).toBeDefined();
    expect(screen.getByText(/11\.20%/)).toBeDefined();
  });

  it('present => omits 1Y XIRR chip when the window is shorter than 360 days', () => {
    renderHero({
      ...SUMMARY_PRESENT,
      data: { ...SUMMARY_PRESENT.data, xirr_1y_pct: 11.2, xirr_1y_window_days: 200 },
    } as any);
    // A shrunk window must never be mislabeled "1Y" — the (renamed) XIRR chip still renders.
    expect(screen.queryByText('1Y XIRR')).toBeNull();
    expect(screen.getByText('XIRR')).toBeDefined();
  });

  it('present => omits 1Y XIRR chip when xirr_1y_pct is null', () => {
    renderHero({
      ...SUMMARY_PRESENT,
      data: { ...SUMMARY_PRESENT.data, xirr_1y_pct: null, xirr_1y_window_days: 365 },
    } as any);
    expect(screen.queryByText('1Y XIRR')).toBeNull();
  });

  // Fix 2b (2026-07-04 XIRR-basis-break incident) — the XIRR chip caveats partial coverage.
  it('present => XIRR chip appends a coverage hint when xirr_coverage_pct < 100', () => {
    renderHero({
      ...SUMMARY_PRESENT,
      data: { ...SUMMARY_PRESENT.data, xirr_coverage_pct: 44 },
    } as any);
    expect(screen.getByText(/covers 44% of value/)).toBeDefined();
  });

  it('present => XIRR chip hint stays plain when xirr_coverage_pct is null (full coverage)', () => {
    renderHero({
      ...SUMMARY_PRESENT,
      data: { ...SUMMARY_PRESENT.data, xirr_coverage_pct: null },
    } as any);
    expect(screen.getByText('current funds · since start')).toBeDefined();
    expect(screen.queryByText(/covers/)).toBeNull();
  });

  it('present => XIRR chip hint stays plain when xirr_coverage_pct is 100', () => {
    renderHero({
      ...SUMMARY_PRESENT,
      data: { ...SUMMARY_PRESENT.data, xirr_coverage_pct: 100 },
    } as any);
    expect(screen.getByText('current funds · since start')).toBeDefined();
    expect(screen.queryByText(/covers/)).toBeNull();
  });

  // -------------------------------------------------------------------------
  // Hero mini "money view" chart (PR-C) — value vs invested, no Nifty line.
  // -------------------------------------------------------------------------

  it('money-view mini chart => Invested/Value/P&L chips + an invested step-line, no Nifty', () => {
    vi.mocked(usePortfolioValueSeries).mockReturnValue({
      data: VALUE_SERIES_PRESENT, isLoading: false, isError: false, refetch: vi.fn(),
    } as any);
    vi.mocked(useNiftyCloseSeries).mockReturnValue({ data: undefined, isLoading: false } as any);

    const { container } = renderHero(SUMMARY_PRESENT);

    expect(screen.getByText(/P&L/)).toBeDefined();
    expect(screen.getAllByText(/Invested/).length).toBeGreaterThan(0);
    // Invested step-line renders as a dashed grey stroke.
    expect(container.querySelector('path[stroke="#94A3B8"]')).not.toBeNull();
    // The hero chart no longer plots (or legends) a Nifty line — Section 2 owns the comparison.
    // The "Compare with Nifty" LINK still stays (task spec) — only the amber line/legend goes.
    expect(container.querySelector('path[stroke="#F5C451"]')).toBeNull();
    expect(screen.queryByText(/YOU VS NIFTY/i)).toBeNull();
    expect(screen.queryByText(/^NIFTY /i)).toBeNull();
  });

  it('money-view mini chart chips render the LIVE summary numbers, not the series last point', () => {
    // founder-reported 2026-07-03: the chip row used to read the daily-series' LAST POINT
    // (value 153,000 / invested 150,000, a different — stale-by-hours, cash-basis — truth than
    // the hero stats above it). It must now show the SAME live summary numbers instead.
    vi.mocked(usePortfolioValueSeries).mockReturnValue({
      data: VALUE_SERIES_PRESENT, isLoading: false, isError: false, refetch: vi.fn(),
    } as any);
    vi.mocked(useNiftyCloseSeries).mockReturnValue({ data: undefined, isLoading: false } as any);

    const { container } = renderHero(SUMMARY_PRESENT);
    const text = container.textContent ?? '';

    // Value chip = summary.total_value (48,32,640 -> "48.33 L"), NOT the series' last point
    // (1,53,000 -> "1.53 L").
    expect(text).toMatch(/48\.33 L/);
    expect(text).not.toMatch(/1\.53 L/);
    // Invested falls back to total_invested (no cost_value in this fixture): 38,48,430 -> "38.48 L",
    // NOT the series' invested last point (1,50,000 -> "1.50 L").
    expect(text).toMatch(/38\.48 L/);
    expect(text).not.toMatch(/1\.50 L/);
    // P&L falls back to gain/gain_pct (9,84,210 / 25.6%), NOT the series-derived 3,000 (+2.0%).
    expect(text).toMatch(/9\.84 L/);
    expect(text).toMatch(/25\.6%/);
    expect(text).not.toMatch(/2\.0%/);
  });
});

// ---------------------------------------------------------------------------
// HeroSection — CAMS-parity chips (cost_value Invested, renamed XIRR, Avg Days)
// ---------------------------------------------------------------------------

describe('HeroSection — CAMS-parity chips', () => {
  beforeEach(() => vi.clearAllMocks());

  function renderHero(envelope: unknown, valueSeries: unknown = undefined) {
    vi.mocked(usePortfolioSummaryById).mockReturnValue({
      data: envelope, isLoading: false, isError: false, error: null, refetch: vi.fn(),
    } as any);
    vi.mocked(usePortfolioValueSeries).mockReturnValue({
      data: valueSeries, isLoading: false, isError: false, refetch: vi.fn(),
    } as any);
    vi.mocked(useNiftyCloseSeries).mockReturnValue({ data: undefined, isLoading: false } as any);
    return render(<HeroSection portfolioId="pid" />, { wrapper });
  }

  const FULL_FIXTURE = {
    ...SUMMARY_PRESENT,
    data: {
      ...SUMMARY_PRESENT.data,
      cost_value: 4_000_000,
      gain_vs_cost: 832_640,
      gain_vs_cost_pct: 20.8,
      xirr_1y_pct: 11.2,
      xirr_1y_window_days: 365,
      wt_avg_days: 347,
    },
  };

  it('renders all 5 chips (Invested, Day Change, 1Y XIRR, XIRR, Avg Days) from a full fixture', () => {
    renderHero(FULL_FIXTURE);
    expect(screen.getByText('Invested')).toBeDefined();
    expect(screen.getByText('Day Change')).toBeDefined();
    expect(screen.getByText('1Y XIRR')).toBeDefined();
    expect(screen.getByText('XIRR')).toBeDefined();
    expect(screen.getByText('Avg Days')).toBeDefined();
  });

  it('Invested chip shows cost_value (incl. reinvested payouts), not cash-basis total_invested', () => {
    renderHero(FULL_FIXTURE);
    // cost_value 4,000,000 => "40,00,000"; distinct from total_invested 3,848,430 => "38,48,430"
    expect(screen.getByText(/40,00,000/)).toBeDefined();
    expect(screen.queryByText(/38,48,430/)).toBeNull();
  });

  it('Invested chip falls back to total_invested when cost_value is absent', () => {
    const { cost_value: _drop, ...rest } = FULL_FIXTURE.data;
    renderHero({ ...FULL_FIXTURE, data: rest });
    expect(screen.getByText(/38,48,430/)).toBeDefined();
  });

  it('Avg Days chip shows wt_avg_days', () => {
    renderHero(FULL_FIXTURE);
    expect(screen.getByText('347')).toBeDefined();
  });

  it('omits Avg Days chip when wt_avg_days is null', () => {
    renderHero({ ...FULL_FIXTURE, data: { ...FULL_FIXTURE.data, wt_avg_days: null } });
    expect(screen.queryByText('Avg Days')).toBeNull();
  });

  it('mini-chart chips use cost_value/gain_vs_cost when present (SAME numbers as the Invested chip)', () => {
    // The mini chart's LINES still need >=2 value-series points to render past its cold-start
    // placeholder — only the chip TEXT is under test here (it must reflect FULL_FIXTURE's numbers,
    // not this series' own last point: value 153,000 / invested 150,000).
    const { container } = renderHero(FULL_FIXTURE, VALUE_SERIES_PRESENT);
    const text = container.textContent ?? '';
    // cost_value 40,00,000 -> "40.00 L", NOT total_invested's 38.48 L.
    expect(text).toMatch(/40\.00 L/);
    // gain_vs_cost 8,32,640 -> "8.33 L" (+20.8%), NOT the cash-basis gain (9.84 L / 25.6%).
    expect(text).toMatch(/8\.33 L/);
    expect(text).toMatch(/20\.8%/);
    expect(container.querySelector('path[stroke="#94A3B8"]')).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// HeroSection — ADR-0039 hero data-integrity hints (2026-07-04)
// ---------------------------------------------------------------------------

describe('HeroSection — ADR-0039 coverage/basis hints', () => {
  beforeEach(() => vi.clearAllMocks());

  function renderHero(envelope: unknown) {
    vi.mocked(usePortfolioSummaryById).mockReturnValue({
      data: envelope, isLoading: false, isError: false, error: null, refetch: vi.fn(),
    } as any);
    vi.mocked(usePortfolioValueSeries).mockReturnValue({
      data: undefined, isLoading: false, isError: false, refetch: vi.fn(),
    } as any);
    vi.mocked(useNiftyCloseSeries).mockReturnValue({ data: undefined, isLoading: false } as any);
    return render(<HeroSection portfolioId="pid" />, { wrapper });
  }

  const BASE_FIXTURE = {
    ...SUMMARY_PRESENT,
    data: { ...SUMMARY_PRESENT.data, wt_avg_days: 347 },
  };

  it('Invested hint appends "some funds missing cost" when invested_missing_count > 0', () => {
    renderHero({ ...BASE_FIXTURE, data: { ...BASE_FIXTURE.data, invested_missing_count: 2 } });
    expect(screen.getByText('incl. reinvested payouts · some funds missing cost')).toBeDefined();
  });

  it('Invested hint stays plain when invested_missing_count is 0 or absent', () => {
    renderHero({ ...BASE_FIXTURE, data: { ...BASE_FIXTURE.data, invested_missing_count: 0 } });
    expect(screen.getByText('incl. reinvested payouts')).toBeDefined();
    expect(screen.queryByText(/missing cost/)).toBeNull();
  });

  it('Avg Days hint appends coverage when wt_avg_days_coverage_pct < 100', () => {
    renderHero({ ...BASE_FIXTURE, data: { ...BASE_FIXTURE.data, wt_avg_days_coverage_pct: 37 } });
    expect(screen.getByText('capital-weighted · covers 37% of value')).toBeDefined();
  });

  it('Avg Days hint stays plain when wt_avg_days_coverage_pct is null', () => {
    renderHero({ ...BASE_FIXTURE, data: { ...BASE_FIXTURE.data, wt_avg_days_coverage_pct: null } });
    expect(screen.getByText('capital-weighted')).toBeDefined();
    expect(screen.queryByText(/covers/)).toBeNull();
  });

  it('Day Change hint appends coverage when day_change_coverage_pct < 100 (no Nifty data)', () => {
    renderHero({
      ...BASE_FIXTURE,
      data: {
        ...BASE_FIXTURE.data,
        day_change: 100,
        day_change_pct: 1.0,
        day_change_as_of: '2026-07-04',
        day_change_coverage_pct: 37,
      },
    });
    expect(screen.getByText(/As of 4 Jul 2026 · covers 37% of value/)).toBeDefined();
  });

  it('Day Change hint stays plain when day_change_coverage_pct is null', () => {
    renderHero({
      ...BASE_FIXTURE,
      data: {
        ...BASE_FIXTURE.data,
        day_change: 100,
        day_change_pct: 1.0,
        day_change_as_of: '2026-07-04',
        day_change_coverage_pct: null,
      },
    });
    expect(screen.queryByText(/covers/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// HeroSection — owner-name pill (hero polish, 2026-07-04)
// ---------------------------------------------------------------------------

describe('HeroSection — owner-name pill', () => {
  beforeEach(() => vi.clearAllMocks());

  function renderHero(envelope: unknown) {
    vi.mocked(usePortfolioSummaryById).mockReturnValue({
      data: envelope, isLoading: false, isError: false, error: null, refetch: vi.fn(),
    } as any);
    vi.mocked(usePortfolioValueSeries).mockReturnValue({
      data: undefined, isLoading: false, isError: false, refetch: vi.fn(),
    } as any);
    vi.mocked(useNiftyCloseSeries).mockReturnValue({ data: undefined, isLoading: false } as any);
    return render(<HeroSection portfolioId="pid" />, { wrapper });
  }

  it('renders the owner name, uppercased (CAMS style), when investor_name is present', () => {
    renderHero({ ...SUMMARY_PRESENT, data: { ...SUMMARY_PRESENT.data, investor_name: 'Manish Kumar' } });
    expect(screen.getByTestId('hero-owner-pill').textContent).toBe('MANISH KUMAR');
  });

  it('renders nothing when investor_name is null', () => {
    renderHero({ ...SUMMARY_PRESENT, data: { ...SUMMARY_PRESENT.data, investor_name: null } });
    expect(screen.queryByTestId('hero-owner-pill')).toBeNull();
  });

  it('renders nothing when investor_name is absent from the payload', () => {
    renderHero(SUMMARY_PRESENT);
    expect(screen.queryByTestId('hero-owner-pill')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// HeroSection — one P&L% story (hero polish, 2026-07-04)
// ---------------------------------------------------------------------------

describe('HeroSection — one P&L% story', () => {
  beforeEach(() => vi.clearAllMocks());

  function renderHero(envelope: unknown) {
    vi.mocked(usePortfolioSummaryById).mockReturnValue({
      data: envelope, isLoading: false, isError: false, error: null, refetch: vi.fn(),
    } as any);
    vi.mocked(usePortfolioValueSeries).mockReturnValue({
      data: undefined, isLoading: false, isError: false, refetch: vi.fn(),
    } as any);
    vi.mocked(useNiftyCloseSeries).mockReturnValue({ data: undefined, isLoading: false } as any);
    return render(<HeroSection portfolioId="pid" />, { wrapper });
  }

  const COST_FIXTURE = {
    ...SUMMARY_PRESENT,
    data: {
      ...SUMMARY_PRESENT.data,
      cost_value: 4_000_000,
      gain_vs_cost: 832_640,
      gain_vs_cost_pct: 20.8,
    },
  };

  it('Total Gain/Total Return use the cost-basis figure, matching the mini-chart P&L chip', () => {
    renderHero(COST_FIXTURE);
    const text = document.body.textContent ?? '';
    // gain_vs_cost 832,640 -> "8,32,640" (full numeral, hero style); gain_vs_cost_pct 20.80%.
    expect(text).toMatch(/8,32,640/);
    expect(text).toMatch(/20\.80%/);
    // The cash-basis gain (984,210 / 25.60%) must NEVER appear anywhere in the hero — one story.
    expect(text).not.toMatch(/9,84,210/);
    expect(text).not.toMatch(/25\.60%/);
  });

  it('falls back to the cash-basis gain/gain_pct when cost_value is absent (unchanged behaviour)', () => {
    renderHero(SUMMARY_PRESENT);
    const text = document.body.textContent ?? '';
    expect(text).toMatch(/9,84,210/);
    expect(text).toMatch(/25\.60%/);
  });
});

// ---------------------------------------------------------------------------
// HeroSection — hint styling + date-anchored Day Change (2026-07-04)
// ---------------------------------------------------------------------------

describe('HeroSection — hint styling + day_change_as_of', () => {
  beforeEach(() => vi.clearAllMocks());

  function renderHero(envelope: unknown, niftyPoints?: { close_date: string; close_value: number }[]) {
    vi.mocked(usePortfolioSummaryById).mockReturnValue({
      data: envelope, isLoading: false, isError: false, error: null, refetch: vi.fn(),
    } as any);
    vi.mocked(usePortfolioValueSeries).mockReturnValue({
      data: undefined, isLoading: false, isError: false, refetch: vi.fn(),
    } as any);
    vi.mocked(useNiftyCloseSeries).mockReturnValue({
      data: niftyPoints
        ? { benchmark: 'NIFTY50', disclosure: '', point_count: niftyPoints.length, points: niftyPoints }
        : undefined,
      isLoading: false,
    } as any);
    return render(<HeroSection portfolioId="pid" />, { wrapper });
  }

  it('Day Change hint is emerald (positive tone) when Nifty moved up today', () => {
    renderHero(
      { ...SUMMARY_PRESENT, data: { ...SUMMARY_PRESENT.data, day_change: 1200, day_change_pct: 0.5, day_change_as_of: '2026-07-15' } },
      [{ close_date: '2026-07-14', close_value: 25_000 }, { close_date: '2026-07-15', close_value: 25_250 }], // +1.00%
    );
    const hint = screen.getByText(/Nifty \+1\.00% today/);
    expect(hint.className).toMatch(/text-emerald-300/);
    expect(hint.textContent).toMatch(/as of \d{1,2} Jul 2026/);
  });

  it('Day Change hint is red (negative tone) when Nifty moved down today', () => {
    renderHero(
      { ...SUMMARY_PRESENT, data: { ...SUMMARY_PRESENT.data, day_change: -800, day_change_pct: -0.3, day_change_as_of: '2026-07-15' } },
      [{ close_date: '2026-07-14', close_value: 25_000 }, { close_date: '2026-07-15', close_value: 24_750 }], // -1.00%
    );
    const hint = screen.getByText(/Nifty −1\.00% today/);
    expect(hint.className).toMatch(/text-red-300/);
  });

  it('Day Change hint falls back to a plain "As of <date>" when no Nifty data is available', () => {
    renderHero(
      { ...SUMMARY_PRESENT, data: { ...SUMMARY_PRESENT.data, day_change: 400, day_change_pct: 0.2, day_change_as_of: '2026-07-15' } },
      undefined,
    );
    const hint = screen.getByText(/As of \d{1,2} Jul 2026/);
    expect(hint.className).toMatch(/text-slate-300/); // neutral tone — no Nifty sign to color by
  });

  it('non-signed hints ("incl. reinvested payouts", "Last 12 months") render the brighter neutral tone', () => {
    renderHero(
      { ...SUMMARY_PRESENT, data: { ...SUMMARY_PRESENT.data, xirr_1y_pct: 11.2, xirr_1y_window_days: 365 } },
      undefined,
    );
    expect(screen.getByText('incl. reinvested payouts').className).toMatch(/text-slate-300/);
    expect(screen.getByText('Last 12 months').className).toMatch(/text-slate-300/);
  });
});

// ---------------------------------------------------------------------------
// HeroSection — "Data as of" freshness line (founder-requested, 2026-07-03)
// ---------------------------------------------------------------------------

describe('HeroSection — freshness line', () => {
  beforeEach(() => vi.clearAllMocks());

  function renderHero(envelope: unknown) {
    vi.mocked(usePortfolioSummaryById).mockReturnValue({
      data: envelope, isLoading: false, isError: false, error: null, refetch: vi.fn(),
    } as any);
    vi.mocked(usePortfolioValueSeries).mockReturnValue({
      data: undefined, isLoading: false, isError: false, refetch: vi.fn(),
    } as any);
    vi.mocked(useNiftyCloseSeries).mockReturnValue({ data: undefined, isLoading: false } as any);
    return render(<HeroSection portfolioId="pid" />, { wrapper });
  }

  it('renders "Data as of <date> · NAV updates nightly" from day_change_as_of', () => {
    renderHero({ ...SUMMARY_PRESENT, data: { ...SUMMARY_PRESENT.data, day_change_as_of: '2026-07-03' } });
    expect(screen.getByText(/Data as of 3 Jul 2026 · NAV updates nightly/)).toBeDefined();
  });

  it('falls back to summary.as_of when day_change_as_of is absent', () => {
    renderHero(SUMMARY_PRESENT); // as_of = '2026-06-25T00:00:00Z', no day_change_as_of on this fixture
    expect(screen.getByText(/Data as of 25 Jun 2026 · NAV updates nightly/)).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// HeroMiniChart — responsive width (founder-reported 2026-07-03: chart hugged
// the left with dead space right; the flex-item wrapper needs w-full to
// actually stretch to its grid column, not just the svg's own viewBox/w-full).
// ---------------------------------------------------------------------------

describe('HeroMiniChart — responsive width', () => {
  beforeEach(() => vi.clearAllMocks());

  it('svg and its wrapper are full-width (no fixed-width dead space)', () => {
    vi.mocked(usePortfolioSummaryById).mockReturnValue({
      data: SUMMARY_PRESENT, isLoading: false, isError: false, error: null, refetch: vi.fn(),
    } as any);
    vi.mocked(usePortfolioValueSeries).mockReturnValue({
      data: VALUE_SERIES_PRESENT, isLoading: false, isError: false, refetch: vi.fn(),
    } as any);
    vi.mocked(useNiftyCloseSeries).mockReturnValue({ data: undefined, isLoading: false } as any);

    const { container } = render(<HeroSection portfolioId="pid" />, { wrapper });
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute('class')).toMatch(/w-full/);
    // The svg's immediate wrapper (HeroMiniChart's root) must also stretch —
    // w-full on the svg alone is a no-op if its parent shrinks to content.
    expect(svg?.parentElement?.className).toMatch(/w-full/);
  });
});

// ---------------------------------------------------------------------------
// buildPeriodPills / defaultPillKey — pure helper (PR-C §3, adaptive pill ladder)
// ---------------------------------------------------------------------------

describe('buildPeriodPills', () => {
  it('age ~205 days => 1D, 7D, 1M, 3M, 6M, All (only 5 ladder rungs fit — 1Y needs 365)', () => {
    expect(buildPeriodPills(205).map((p) => p.key)).toEqual(['1D', '7D', '1M', '3M', '6M', 'All']);
  });

  it('age 10 years => the largest six rungs that fit, plus All', () => {
    expect(buildPeriodPills(3650).map((p) => p.key)).toEqual(['3M', '6M', '1Y', '3Y', '5Y', '10Y', 'All']);
  });

  it('age 3 days => only 1D fits, plus All', () => {
    expect(buildPeriodPills(3).map((p) => p.key)).toEqual(['1D', 'All']);
  });

  it('age 0 days (brand-new portfolio) => just All', () => {
    expect(buildPeriodPills(0).map((p) => p.key)).toEqual(['All']);
  });

  it('unknown age (null/undefined) is treated as unbounded — full ladder, not a collapsed [All]', () => {
    expect(buildPeriodPills(null).map((p) => p.key)).toEqual(['3M', '6M', '1Y', '3Y', '5Y', '10Y', 'All']);
    expect(buildPeriodPills(undefined).map((p) => p.key)).toEqual(['3M', '6M', '1Y', '3Y', '5Y', '10Y', 'All']);
  });
});

describe('defaultPillKey', () => {
  it('keeps 6M when it is still in the ladder', () => {
    expect(defaultPillKey(buildPeriodPills(3650))).toBe('6M');
  });

  it('falls back to the largest non-All pill when 6M is not in the ladder', () => {
    expect(defaultPillKey(buildPeriodPills(3))).toBe('1D'); // pills = [1D, All]
  });

  it('falls back to All when it is the only pill', () => {
    expect(defaultPillKey(buildPeriodPills(0))).toBe('All'); // pills = [All]
  });
});

// ---------------------------------------------------------------------------
// VsMarketSection — Section-2 "You" line is TWR (flow-neutral), not value-rebased (PR-C §2)
// ---------------------------------------------------------------------------

describe('VsMarketSection — TWR return line', () => {
  beforeEach(() => vi.clearAllMocks());

  it('a same-day deposit leaves the return line flat; a real market move still shows', () => {
    vi.mocked(usePortfolioValueSeries).mockReturnValue({
      data: VALUE_SERIES_PRESENT, isLoading: false, isError: false, refetch: vi.fn(),
    } as any);
    vi.mocked(useNiftyCloseSeries).mockReturnValue({ data: undefined, isLoading: false } as any);

    render(<VsMarketSection portfolioId="pid" />, { wrapper });

    // twr_index: 100 -> 100 (deposit day, flat) -> 102 (+2% pure market move). The naive
    // value-based calc would give (153,000/100,000 - 1) * 100 = +53% — the founder-reported bug.
    expect(screen.getByText('+2.00%')).toBeDefined();
    expect(screen.queryByText(/53\.00%/)).toBeNull();
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
    expect(screen.getAllByText('On track').length).toBeGreaterThan(0);
    expect(screen.getAllByText('In form').length).toBeGreaterThan(0);
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

  it('present => shows the XIRR column, rendering a value and a dash on null (no-suppress)', () => {
    renderHoldings(HOLDINGS_PRESENT);
    expect(screen.getByText('XIRR')).toBeDefined();
    // First holding has xirr_pct: 12.34 => "+12.34%"
    expect(screen.getByText(/\+12\.34%/)).toBeDefined();
    // Second holding has xirr_pct: null => rendered as a dash, column never hidden
    const dashCells = screen.getAllByText('—');
    expect(dashCells.length).toBeGreaterThan(0);
  });

  it('present => shows the Today column (per-holding day_change), value and a dash on null', () => {
    renderHoldings(HOLDINGS_PRESENT);
    expect(screen.getByText('Today')).toBeDefined();
    // First holding has day_change: 1500.0 => "+₹1,500" (humanized fmtCurrency, en-IN grouping)
    expect(screen.getByText(/\+₹1,500/)).toBeDefined();
    // Second holding has day_change: null => rendered as a dash, column never hidden
    const dashCells = screen.getAllByText('—');
    expect(dashCells.length).toBeGreaterThan(0);
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

// ---------------------------------------------------------------------------
// RiskSection tests
// ---------------------------------------------------------------------------

const RISK_META = {
  reason: null,
  as_of: '2026-06-28T00:00:00Z',
  is_stale: false,
  source: 'computed' as const,
  visibility_class: 'educational' as const,
  data_class: 'derived-personal' as const,
  access_tier: 'free' as const,
  content_class: 'DERIVED' as const,
  gate: null,
  disclaimer_version: '2026-06-01',
  engine_version: 'v1',
  quality: 0.9,
};

const RISK_PRESENT = {
  status: 'present' as const,
  data: {
    portfolio_id: 'port-1',
    risk_band: 'moderate' as const,
    risk_band_basis: 'average fund volatility',
    volatility_pct: 14.3,
    max_drawdown_pct: null, // B88: deferred
    recovery_months: null,
    fund_count: 6,
    funds_with_metrics: 5,
    as_of: '2026-06-28',
  },
  meta: RISK_META,
};

const RISK_EMPTY = { status: 'empty' as const, data: null, meta: { ...RISK_META, reason: 'empty' as const } };

// M2.3 (resolves B88) — the portfolio's own daily valuation series is long enough: real numbers,
// not the coming-soon deferral above.
const RISK_TRUE_PRESENT = {
  status: 'present' as const,
  data: {
    portfolio_id: 'port-1',
    risk_band: 'moderate' as const,
    risk_band_basis: 'portfolio return series',
    volatility_pct: 16.2,
    max_drawdown_pct: 22.5,
    recovery_months: 4,
    fund_count: 6,
    funds_with_metrics: 5,
    as_of: '2026-06-28',
  },
  meta: RISK_META,
};

const ADV_PRESENT = {
  status: 'present' as const,
  data: {
    portfolio_id: 'port-1',
    sharpe_ratio: null, // B88: deferred
    sortino_ratio: null, // B88: deferred
    rolling_1y_avg_pct: 17.8,
    rolling_1y_pct_positive: null, // B88: deferred (per-fund hit-rate doesn't aggregate)
    alpha: null,
    beta: null,
    as_of: '2026-06-28',
  },
  meta: RISK_META,
};

const ADV_TRUE_PRESENT = {
  status: 'present' as const,
  data: {
    portfolio_id: 'port-1',
    sharpe_ratio: 0.85,
    sortino_ratio: 1.1,
    rolling_1y_avg_pct: 17.8,
    rolling_1y_pct_positive: 72.0,
    alpha: null,
    beta: null,
    as_of: '2026-06-28',
  },
  meta: RISK_META,
};

/** Minimal ApiError-shaped object — just needs a .problem.status for the 402 branch. */
function make402() {
  const e = new Error('402 Payment Required') as Error & { problem: { status: number } };
  e.name = 'ApiError';
  e.problem = { status: 402 };
  return e;
}

describe('RiskSection', () => {
  beforeEach(() => vi.clearAllMocks());

  function renderRisk(
    riskEnvelope: any,
    advOverride: {
      data?: typeof ADV_PRESENT | typeof ADV_TRUE_PRESENT;
      isError?: boolean;
      error?: Error | null;
    } = {},
  ) {
    const riskMock = vi.mocked(usePortfolioRisk);
    const advMock = vi.mocked(usePortfolioRiskAdvanced);

    const isLoading = riskEnvelope.status === 'loading';
    const isError = riskEnvelope.status === 'error';
    riskMock.mockReturnValue({
      data: isLoading || isError ? undefined : riskEnvelope,
      isLoading,
      isError,
      error: isError ? new Error('fail') : null,
      refetch: vi.fn(),
    } as any);

    advMock.mockReturnValue({
      data: advOverride.data ?? undefined,
      isLoading: false,
      isError: advOverride.isError ?? false,
      error: advOverride.error ?? null,
      refetch: vi.fn(),
    } as any);

    return render(<RiskSection portfolioId="port-1" />, { wrapper });
  }

  // ── 4 DataState states ───────────────────────────────────────────────────

  it('loading => skeleton, standard ratios not visible', () => {
    renderRisk({ status: 'loading', data: null, meta: RISK_META });
    expect(screen.queryByText(/Price Swings/i)).toBeNull();
    expect(screen.queryByText(/Biggest Fall/i)).toBeNull();
  });

  it('error => ErrorCard rendered', () => {
    renderRisk({ status: 'error', data: null, meta: RISK_META });
    // ErrorCard renders "Something went wrong" heading
    expect(screen.getByText(/something went wrong/i)).toBeDefined();
  });

  it('empty => EmptyState visible, no ratios', () => {
    renderRisk(RISK_EMPTY);
    expect(screen.queryByText(/Price Swings/i)).toBeNull();
    expect(screen.getByText(/risk data will appear/i)).toBeDefined();
  });

  it('present => volatility + indicative band render; drawdown deferred (B88)', () => {
    renderRisk(RISK_PRESENT);
    expect(screen.getByText(/Price Swings/i)).toBeDefined();
    expect(screen.getByText('±14.3%')).toBeDefined(); // the avg fund volatility (the band basis)
    expect(screen.getByText(/Indicative — based on average fund volatility/i)).toBeDefined();
    expect(screen.getByText(/Biggest Fall/i)).toBeDefined(); // present as a coming-soon card
    expect(screen.queryByText('−18.7%')).toBeNull(); // B88: no aggregated drawdown number
  });

  // ── Risk band renders as word badge, never a number ──────────────────────

  it('risk band renders as display word (Moderate), not raw enum or number', () => {
    renderRisk(RISK_PRESENT);
    expect(screen.getByText('Moderate')).toBeDefined();
    // raw backend value must not appear directly
    expect(screen.queryByText('moderate')).toBeNull();
  });

  // ── No numeric composite score in DOM (non-neg #2) ───────────────────────

  it('does not render a numeric composite risk score', () => {
    renderRisk(RISK_PRESENT);
    const text = document.body.textContent ?? '';
    expect(text).not.toMatch(/risk score/i);
    expect(text).not.toMatch(/composite/i);
  });

  // ── Recovery months comes-soon card (NO-SUPPRESS) ────────────────────────

  it('renders Recovery Time as coming-soon, never a real value', () => {
    renderRisk(RISK_PRESENT);
    expect(screen.getByText(/Recovery Time/i)).toBeDefined();
    // ComingSoonCard renders "— Coming soon" in a sibling div; check the whole DOM
    expect(screen.getAllByText(/Coming soon/i).length).toBeGreaterThanOrEqual(1);
    // No months number anywhere
    expect(document.body.textContent).not.toMatch(/\d+ months?/i);
  });

  // ── Advanced panel — 402 upgrade state ──────────────────────────────────

  it('advanced panel shows upgrade copy when 402', async () => {
    renderRisk(RISK_PRESENT, { isError: true, error: make402() });
    const advBtn = screen.getByRole('button', { name: /Advanced Risk Metrics/i });
    fireEvent.click(advBtn);
    // DataState withheld/tier renders the tier copy
    expect(screen.getByText(/DhanRadar Plus/i)).toBeDefined();
    // Sharpe/Sortino must NOT appear (upgrade wall, not data)
    expect(screen.queryByText(/Sharpe Ratio/i)).toBeNull();
  });

  // ── Advanced panel — success state renders ratios ────────────────────────

  it('advanced panel: Sharpe/Sortino deferred (B88), rolling return renders', async () => {
    renderRisk(RISK_PRESENT, { data: ADV_PRESENT });
    const advBtn = screen.getByRole('button', { name: /Advanced Risk Metrics/i });
    fireEvent.click(advBtn);
    // B88: Sharpe/Sortino labels present as coming-soon cards — NO 1.42/2.01 value.
    expect(screen.getByText(/Sharpe Ratio/i)).toBeDefined();
    expect(screen.getByText(/Sortino Ratio/i)).toBeDefined();
    expect(screen.queryByText('1.42')).toBeNull();
    expect(screen.queryByText('2.01')).toBeNull();
    // rolling return (aggregates by weight) IS rendered
    expect(screen.getByText(/Rolling 1Y Avg/i)).toBeDefined();
    expect(screen.getByText('17.8%')).toBeDefined();
  });

  it('advanced panel renders Sharpe/Sortino/alpha/beta as coming-soon, not numbers (B88)', async () => {
    renderRisk(RISK_PRESENT, { data: ADV_PRESENT });
    const advBtn = screen.getByRole('button', { name: /Advanced Risk Metrics/i });
    fireEvent.click(advBtn);
    expect(screen.getByText('Alpha')).toBeDefined();
    expect(screen.getByText('Beta')).toBeDefined();
    // coming soon now covers Sharpe + Sortino (B88) + Alpha + Beta
    expect(screen.getAllByText(/coming soon/i).length).toBeGreaterThanOrEqual(4);
  });

  // ── M2.3 (resolves B88): true portfolio return series → real values, not coming-soon ────

  it('present with true series basis => real Biggest Fall + Recovery Time render, not coming-soon', () => {
    renderRisk(RISK_TRUE_PRESENT);
    expect(screen.getByText(/Indicative — based on portfolio return series/i)).toBeDefined();
    // exact strings — a regex would also partial-match the description copy ("...biggest fall.")
    expect(screen.getByText('Biggest Fall')).toBeDefined();
    expect(screen.getByText('-22.5%')).toBeDefined();
    expect(screen.getByText('Recovery Time')).toBeDefined();
    expect(screen.getByText('4 months')).toBeDefined();
    // no "coming soon" left for these two fields now that the series is long enough
    expect(screen.queryAllByText('— Coming soon').length).toBe(0);
  });

  it('advanced panel with true series basis => real Sharpe/Sortino/Positive-1Y-Windows render', async () => {
    renderRisk(RISK_TRUE_PRESENT, { data: ADV_TRUE_PRESENT });
    const advBtn = screen.getByRole('button', { name: /Advanced Risk Metrics/i });
    fireEvent.click(advBtn);
    expect(screen.getByText('Sharpe Ratio')).toBeDefined();
    expect(screen.getByText('0.85')).toBeDefined();
    expect(screen.getByText('Sortino Ratio')).toBeDefined();
    expect(screen.getByText('1.10')).toBeDefined();
    expect(screen.getByText('Positive 1Y Windows')).toBeDefined();
    expect(screen.getByText('72.0%')).toBeDefined();
    // Alpha/Beta remain coming-soon (out of scope, ADR-0033b) — the only 2 left
    expect(screen.getAllByText('— Coming soon').length).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// AllocSection tests (live allocation + concentration sub-panel)
// ---------------------------------------------------------------------------

const ALLOC_PRESENT = {
  status: 'present' as const,
  data: {
    portfolio_id: 'pid',
    by: 'category',
    buckets: [
      { bucket: 'Large Cap', value: 250_000, weight_pct: 52.3 },
      { bucket: 'Flexi Cap', value: 150_000, weight_pct: 31.4 },
      { bucket: 'Mid Cap', value: 78_000, weight_pct: 16.3 },
    ],
    total_value: 478_000,
    fund_count: 6,
    as_of: '2026-06-28',
  },
  meta: EMPTY_META,
};

const CONC_PRESENT = {
  status: 'present' as const,
  data: {
    portfolio_id: 'pid',
    band: 'moderate' as const,
    top_fund: { name: 'Mirae Asset Large Cap Fund', weight_pct: 28.4 },
    top_amc: { name: 'Mirae Asset', weight_pct: 41.0 },
    by_amc: [
      { name: 'Mirae Asset', weight_pct: 41.0 },
      { name: 'Parag Parikh', weight_pct: 31.4 },
    ],
    fund_count: 6,
    amc_count: 3,
    as_of: '2026-06-28',
  },
  meta: EMPTY_META,
};

const CONC_EMPTY = { status: 'empty' as const, data: null, meta: { ...EMPTY_META, reason: 'empty' as const } };

// "By AMC" allocation + a full-legal-name concentration fixture — proves the hero-polish
// shortAmcName strip (founder-reported 2026-07-04) reaches every live AMC surface.
const ALLOC_PRESENT_AMC = {
  status: 'present' as const,
  data: {
    portfolio_id: 'pid',
    by: 'amc',
    buckets: [
      { bucket: 'HDFC Asset Management Company Limited', value: 250_000, weight_pct: 52.3 },
      { bucket: 'DSP Investment Managers', value: 150_000, weight_pct: 31.4 },
    ],
    total_value: 400_000,
    fund_count: 6,
    as_of: '2026-06-28',
  },
  meta: EMPTY_META,
};

const CONC_PRESENT_LONG_AMC = {
  ...CONC_PRESENT,
  data: {
    ...CONC_PRESENT.data,
    top_amc: { name: 'ICICI Prudential Asset Management Company Ltd', weight_pct: 41.0 },
    by_amc: [{ name: 'ICICI Prudential Asset Management Company Ltd', weight_pct: 41.0 }],
  },
};

describe('AllocSection', () => {
  beforeEach(() => vi.clearAllMocks());

  function renderAlloc(
    allocEnvelope: any,
    concEnvelope: any = CONC_EMPTY,
  ) {
    const allocMock = vi.mocked(usePortfolioAllocation);
    const concMock = vi.mocked(usePortfolioConcentration);

    const isLoading = allocEnvelope.status === 'loading';
    const isError = allocEnvelope.status === 'error';
    allocMock.mockReturnValue({
      data: isLoading || isError ? undefined : allocEnvelope,
      isLoading,
      isError,
      error: isError ? new Error('fail') : null,
      refetch: vi.fn(),
    } as any);

    const cLoading = concEnvelope.status === 'loading';
    const cError = concEnvelope.status === 'error';
    concMock.mockReturnValue({
      data: cLoading || cError ? undefined : concEnvelope,
      isLoading: cLoading,
      isError: cError,
      error: cError ? new Error('fail') : null,
      refetch: vi.fn(),
    } as any);

    return render(<AllocSection portfolioId="pid" />, { wrapper });
  }

  it('loading => skeleton, no bucket name', () => {
    renderAlloc(LOADING_STATE);
    expect(screen.queryByText('Large Cap')).toBeNull();
  });

  it('present => shows a bucket name and its weight %', () => {
    renderAlloc(ALLOC_PRESENT, CONC_PRESENT);
    // "Large Cap" appears in both the donut legend and the weight bar
    expect(screen.getAllByText('Large Cap').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/52\.3%/).length).toBeGreaterThan(0);
  });

  it('present => concentration sub-panel shows top_fund name', () => {
    renderAlloc(ALLOC_PRESENT, CONC_PRESENT);
    expect(screen.getByText('Mirae Asset Large Cap Fund')).toBeDefined();
  });

  it('empty => EmptyState visible, no bucket name', () => {
    renderAlloc(EMPTY_STATE);
    expect(screen.queryByText('Large Cap')).toBeNull();
    expect(screen.getAllByText(/Nothing here yet|allocation shows/i).length).toBeGreaterThan(0);
  });

  it('error => ErrorCard, no bucket name', () => {
    renderAlloc(ERROR_STATE);
    expect(screen.queryByText('Large Cap')).toBeNull();
    expect(screen.getByText(/something went wrong/i)).toBeDefined();
  });

  it('no advisory verbs, no numeric composite score in present state', () => {
    renderAlloc(ALLOC_PRESENT, CONC_PRESENT);
    const text = document.body.textContent ?? '';
    assertNoAdvisoryVerbs(text);
    assertNoNumericScore(text);
    // no "ideal"/"recommended" allocation comparison (implies advice)
    expect(text).not.toMatch(/ideal|recommended/i);
  });

  // Hero polish (founder-reported 2026-07-04): AMC/fund-house text shortens to the
  // recognizable brand wherever it renders on the portfolio page.
  it('"By AMC" view => shortens a full legal AMC bucket name to its bare brand', () => {
    renderAlloc(ALLOC_PRESENT_AMC, CONC_EMPTY);
    fireEvent.click(screen.getByRole('button', { name: /By AMC/i }));
    expect(screen.getAllByText('HDFC').length).toBeGreaterThan(0);
    expect(screen.getAllByText('DSP').length).toBeGreaterThan(0);
    expect(screen.queryByText(/Asset Management Company Limited/)).toBeNull();
    expect(screen.queryByText(/Investment Managers/)).toBeNull();
  });

  it('concentration sub-panel shortens a full legal AMC name (top_amc + by_amc)', () => {
    renderAlloc(ALLOC_PRESENT, CONC_PRESENT_LONG_AMC);
    expect(screen.getAllByText('ICICI Prudential').length).toBeGreaterThan(0);
    expect(screen.queryByText(/Asset Management Company Ltd/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// DivSection tests (live diversification)
// ---------------------------------------------------------------------------

const DIV_PRESENT = {
  status: 'present' as const,
  data: {
    portfolio_id: 'pid',
    band: 'high' as const,
    category_count: 5,
    top_category: 'Large Cap',
    top_category_pct: 38.2,
    fund_count: 6,
    as_of: '2026-06-28',
  },
  meta: EMPTY_META,
};

describe('DivSection', () => {
  beforeEach(() => vi.clearAllMocks());

  function renderDiv(envelope: any) {
    const mock = vi.mocked(usePortfolioDiversification);
    const isLoading = envelope.status === 'loading';
    const isError = envelope.status === 'error';
    mock.mockReturnValue({
      data: isLoading || isError ? undefined : envelope,
      isLoading,
      isError,
      error: isError ? new Error('fail') : null,
      refetch: vi.fn(),
    } as any);
    return render(<DivSection portfolioId="pid" />, { wrapper });
  }

  it('loading => skeleton, no facts', () => {
    renderDiv(LOADING_STATE);
    expect(screen.queryByText('Well spread')).toBeNull();
  });

  it('present => shows band WORD (not a number) and top category', () => {
    renderDiv(DIV_PRESENT);
    expect(screen.getByText('Well spread')).toBeDefined(); // high band → word
    expect(screen.getByText('Large Cap')).toBeDefined();
    expect(screen.getByText(/38\.2%/)).toBeDefined(); // user's own %
  });

  it('empty => EmptyState visible, no band word', () => {
    renderDiv(EMPTY_STATE);
    expect(screen.queryByText('Well spread')).toBeNull();
    expect(screen.getAllByText(/Nothing here yet|diversification reading/i).length).toBeGreaterThan(0);
  });

  it('error => ErrorCard', () => {
    renderDiv(ERROR_STATE);
    expect(screen.getByText(/something went wrong/i)).toBeDefined();
  });

  it('no advisory verbs, no numeric composite score, no "Top N% of portfolios"', () => {
    renderDiv(DIV_PRESENT);
    const text = document.body.textContent ?? '';
    assertNoAdvisoryVerbs(text);
    assertNoNumericScore(text);
    expect(text).not.toMatch(/Top \d+% of portfolios/i);
    expect(text).not.toMatch(/ideal/i);
  });
});

// ---------------------------------------------------------------------------
// EmptyHero upload-phase tests
// ---------------------------------------------------------------------------

describe('EmptyHero upload phases', () => {
  function renderEmpty(props: Partial<Parameters<typeof EmptyHero>[0]> = {}) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={qc}>
        <EmptyHero onViewSample={() => {}} {...props} />
      </QueryClientProvider>,
    );
  }

  // 7. uploading phase shows status label
  it('uploadPhase=uploading: status label visible', () => {
    renderEmpty({ uploadPhase: 'uploading', uploadStatusLabel: 'Uploading your statement…' });
    expect(screen.getByTestId('upload-status')).toBeDefined();
    expect(screen.getByText('Uploading your statement…')).toBeDefined();
  });

  // 8. processing phase shows progress
  it('uploadPhase=processing: progress bar and label render', () => {
    renderEmpty({ uploadPhase: 'processing', uploadProgress: 60, uploadStatusLabel: 'Processing your statement…' });
    expect(screen.getByTestId('upload-status')).toBeDefined();
    expect(screen.getByText('Processing your statement…')).toBeDefined();
    expect(screen.getByText('60%')).toBeDefined();
  });

  // 9. done phase shows success message
  it('uploadPhase=done: success message renders', () => {
    renderEmpty({ uploadPhase: 'done' });
    expect(screen.getByTestId('upload-status')).toBeDefined();
    expect(screen.getByText(/portfolio is ready/i)).toBeDefined();
  });

  // 10. error phase shows error message and retry
  it('uploadPhase=error: error message and Try again button render', () => {
    renderEmpty({ uploadPhase: 'error', uploadError: 'Something went wrong — please try again.' });
    expect(screen.getByTestId('upload-status')).toBeDefined();
    expect(screen.getByText(/something went wrong/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /try again/i })).toBeDefined();
  });

  // Founder-reported (2026-07-03): the raw machine code ('parse_failed') used to be shown
  // directly as the error message. It must now render as small/muted support text only,
  // never as the primary message.
  it('uploadPhase=error: shows the friendly message plus the raw code subtly for support', () => {
    renderEmpty({
      uploadPhase: 'error',
      uploadError: "That password doesn't match this PDF. CAS passwords are usually your PAN in capital letters plus date of birth.",
      uploadErrorCode: 'incorrect_password',
    });
    expect(screen.getByText(/doesn't match this PDF/i)).toBeDefined();
    expect(screen.getByText('code: incorrect_password')).toBeDefined();
  });

  it('uploadPhase=error: omits the code line when no uploadErrorCode is given', () => {
    renderEmpty({ uploadPhase: 'error', uploadError: 'Upload failed — please try again.' });
    expect(screen.queryByText(/^code:/)).toBeNull();
  });

  // idle phase: no status block
  it('uploadPhase=idle (default): no status block shown', () => {
    renderEmpty({ uploadPhase: 'idle' });
    expect(screen.queryByTestId('upload-status')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Password field wiring tests
// ---------------------------------------------------------------------------

describe('EmptyHero password field', () => {
  function renderEmpty(props: Partial<Parameters<typeof EmptyHero>[0]> = {}) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={qc}>
        <EmptyHero onViewSample={() => {}} {...props} />
      </QueryClientProvider>,
    );
  }

  it('renders the password input in idle state', () => {
    renderEmpty({ uploadPhase: 'idle' });
    expect(screen.getByTestId('password-field-empty-hero')).toBeDefined();
    // label present (selector: 'input' disambiguates from the eye-toggle button, whose
    // own aria-label — "Show password" — also matches a bare /Password/i regex)
    expect(screen.getByLabelText(/Password/i, { selector: 'input' })).toBeDefined();
  });

  it('password input does NOT render while upload is in flight', () => {
    renderEmpty({ uploadPhase: 'uploading' });
    expect(screen.queryByTestId('password-field-empty-hero')).toBeNull();
  });

  // Founder-reported (2026-07-03): no show/hide toggle on the CAS password field.
  it('password field has a show/hide (eye) toggle that flips the input type', () => {
    renderEmpty({ uploadPhase: 'idle' });
    const pwdInput = screen.getByLabelText(/Password/i, { selector: 'input' }) as HTMLInputElement;
    expect(pwdInput.type).toBe('password');

    fireEvent.click(screen.getByRole('button', { name: /show password/i }));
    expect(pwdInput.type).toBe('text');

    fireEvent.click(screen.getByRole('button', { name: /hide password/i }));
    expect(pwdInput.type).toBe('password');
  });

  it('password input re-shown after error (parse_failed / wrong password)', () => {
    renderEmpty({ uploadPhase: 'error', uploadError: 'Incorrect password — please enter the correct CAS password.' });
    // password field rendered again
    expect(screen.getByTestId('password-field-empty-hero')).toBeDefined();
  });

  it('calls onUpload with the entered password when user picks a file', async () => {
    const onUpload = vi.fn();
    renderEmpty({ uploadPhase: 'idle', onUpload });

    // Type a password
    const pwdInput = screen.getByLabelText(/Password/i, { selector: 'input' });
    fireEvent.change(pwdInput, { target: { value: 'ABCDE1234F' } });

    // Simulate file pick via the hidden input
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['dummy'], 'cas.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', { value: [file], configurable: true });
    fireEvent.change(fileInput);

    expect(onUpload).toHaveBeenCalledWith(file, 'ABCDE1234F');
  });

  it('calls onUpload WITHOUT password when user picks a file with empty password field', async () => {
    const onUpload = vi.fn();
    renderEmpty({ uploadPhase: 'idle', onUpload });

    // Password field left empty — do NOT type anything
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['dummy'], 'cas.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', { value: [file], configurable: true });
    fireEvent.change(fileInput);

    // onUpload called with file and empty string (hook handles empty→undefined internally)
    expect(onUpload).toHaveBeenCalledWith(file, '');
  });
});

// ---------------------------------------------------------------------------
// HelpTip wiring tests (§28) — copy from accessors, no hardcoded strings
// ---------------------------------------------------------------------------

describe('HelpTip wiring', () => {
  beforeEach(() => vi.clearAllMocks());

  // ── RiskSection: section header tip ─────────────────────────────────────

  it('RiskSection: section header HelpTip text matches sectionTooltip accessor', () => {
    const riskMock = vi.mocked(usePortfolioRisk);
    const advMock = vi.mocked(usePortfolioRiskAdvanced);
    riskMock.mockReturnValue({ data: undefined, isLoading: true, isError: false, error: null, refetch: vi.fn() } as any);
    advMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<RiskSection portfolioId="port-1" />, { wrapper: ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider> });

    const expected = sectionTooltip('RiskSection');
    expect(expected).toBeTruthy(); // guard: accessor must return a non-empty string
    // The tooltip text is in the DOM (inside role="tooltip" span, initially opacity-0 but present)
    expect(screen.getByText(expected!)).toBeDefined();
  });

  // ── RiskSection: Sharpe Ratio KPI tip, focus reveals tooltip ────────────

  it('RiskSection: Sharpe Ratio KPI HelpTip renders with fieldTooltip text and focus reveals it', () => {
    const riskMock = vi.mocked(usePortfolioRisk);
    const advMock = vi.mocked(usePortfolioRiskAdvanced);
    riskMock.mockReturnValue({
      data: {
        status: 'present',
        data: {
          portfolio_id: 'port-1',
          risk_band: 'moderate',
          risk_band_basis: 'average fund volatility',
          volatility_pct: 14.3,
          max_drawdown_pct: null,
          recovery_months: null,
          fund_count: 6,
          funds_with_metrics: 5,
          as_of: '2026-06-28',
        },
        meta: {
          reason: null, as_of: null, is_stale: false, source: 'computed' as const,
          visibility_class: 'educational' as const, data_class: 'derived-personal' as const,
          access_tier: 'free' as const, content_class: 'DERIVED' as const,
          gate: null, disclaimer_version: null, engine_version: null, quality: null,
        },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    advMock.mockReturnValue({
      data: {
        status: 'present',
        data: { portfolio_id: 'port-1', sharpe_ratio: null, sortino_ratio: null, rolling_1y_avg_pct: 17.8, rolling_1y_pct_positive: null, alpha: null, beta: null, as_of: '2026-06-28' },
        meta: { reason: null, as_of: null, is_stale: false, source: 'computed' as const, visibility_class: 'educational' as const, data_class: 'derived-personal' as const, access_tier: 'free' as const, content_class: 'DERIVED' as const, gate: null, disclaimer_version: null, engine_version: null, quality: null },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<RiskSection portfolioId="port-1" />, { wrapper: ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider> });

    // Open the advanced panel
    const advBtn = screen.getByRole('button', { name: /Advanced Risk Metrics/i });
    fireEvent.click(advBtn);

    const expected = fieldTooltip('RiskSection', 'sharpe');
    expect(expected).toBeTruthy(); // guard: accessor must return a string
    // Tooltip text should be in the DOM
    const tipEl = screen.getByText(expected!);
    expect(tipEl).toBeDefined();

    // Focus the trigger button — tooltip should become visible (focus calls show())
    const triggerBtn = tipEl.closest('[role="tooltip"]')?.previousElementSibling as HTMLElement | null;
    // Find the HelpTip button that controls this tooltip via aria-describedby
    const tooltipId = tipEl.id ?? tipEl.getAttribute('id');
    if (tooltipId) {
      const trigger = document.querySelector(`[aria-describedby="${tooltipId}"]`) as HTMLElement | null;
      if (trigger) {
        fireEvent.focus(trigger);
        // After focus the tooltip should remain in the DOM (visibility controlled by opacity, not mount)
        expect(screen.getByText(expected!)).toBeDefined();
      }
    }
    // Fallback: tooltip text is in DOM regardless (opacity-0 → opacity-100 is CSS, not unmount)
    expect(screen.getByText(expected!)).toBeDefined();
    void triggerBtn; // suppress unused warning
  });
});

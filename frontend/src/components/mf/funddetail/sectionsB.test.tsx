/**
 * vitest tests for two fund-page-quick-wins fixes (mirrors sectionsA.test.tsx's
 * mocked-hooks convention):
 *
 * Fix 1 — Returns-tab "vs benchmark & category" comparison table (PerformanceSection,
 *   default tab). Verifies the three rows (This fund / Benchmark / Category avg) render
 *   real head/benchmark-returns/category-percentile data, never the old sampleData
 *   preview numbers, and the table no longer carries a <PreviewBadge/>.
 *
 * Fix 2 — Risk Center advanced-ratio stat-to-sentence coverage (RiskCenterSection).
 *   Verifies a Max Drawdown sentence appears when a category percentile band is
 *   served, and that Sharpe/Sortino NEVER get a fabricated sentence (no honest
 *   category-relative basis exists for either metric today).
 */

import * as React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PerformanceSection, RiskCenterSection, SnapshotSection } from './sectionsB';
import type { FundHead } from './sectionsHero';

const mockUseFundNav = vi.fn();
const mockUseFundAnalytics = vi.fn();
const mockUseFundSip = vi.fn();
const mockUseFundPeople = vi.fn();
const mockUseFundComparison = vi.fn();
const mockUseBenchmarkSeries = vi.fn();
const mockUseBenchmarkReturns = vi.fn();

vi.mock('@/features/mf/api', () => ({
  useFundNav: (...args: unknown[]) => mockUseFundNav(...args),
  useFundAnalytics: (...args: unknown[]) => mockUseFundAnalytics(...args),
  useFundSip: (...args: unknown[]) => mockUseFundSip(...args),
  useFundPeople: (...args: unknown[]) => mockUseFundPeople(...args),
  useFundComparison: (...args: unknown[]) => mockUseFundComparison(...args),
}));

vi.mock('@/features/portfolio/api', () => ({
  useBenchmarkSeries: (...args: unknown[]) => mockUseBenchmarkSeries(...args),
  useBenchmarkReturns: (...args: unknown[]) => mockUseBenchmarkReturns(...args),
}));

const ISIN = 'INF200K01VT2';

const HEAD: FundHead = {
  name: 'Test Fund',
  amc: 'Test AMC',
  category: 'Equity Scheme - Large Cap Fund',
  label: 'on_track',
  band: 'medium',
  rank: 3,
  total: 20,
  planOption: ['Direct', 'Growth'],
  aumCr: 5000,
  navLatest: 120,
  navDate: '2026-06-30',
  navChangePct: 0.5,
  expenseRatioPct: 0.75,
  return3mPct: 4.1,
  return6mPct: 7.2,
  return1yPct: 12.3,
  return3yPct: 45.6,
  return5yPct: 78.9,
  launchDate: '2018-03-15',
  fundAumCr: 1200,
  fundAumAsOf: '2026-06-01',
};

function emptyDataEnvelope() {
  return { status: 'empty', data: null, meta: { reason: null } };
}

describe('Returns tab comparison table (Fix 1)', () => {
  it('renders real This fund / Benchmark / Category avg rows, no PreviewBadge', () => {
    mockUseFundNav.mockReturnValue({ data: undefined, isLoading: false });
    mockUseFundSip.mockReturnValue({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() });
    mockUseBenchmarkSeries.mockReturnValue({ data: undefined });
    mockUseBenchmarkReturns.mockReturnValue({
      data: {
        benchmark: 'nifty100',
        display_name: 'Nifty 100',
        disclosure: 'Nifty 100 · price index, excludes dividends',
        return_1y_pct: 10.0,
        return_3y_pct: 30.0,
        return_5y_pct: null,
        as_of: '2026-06-30',
      },
    });
    mockUseFundAnalytics.mockReturnValue({
      data: {
        analytics: {
          status: 'present',
          data: {
            category_percentiles: {
              return_1y_pct: { p25: 5.0, p50: 9.5, p75: 15.0, p90: 20.0 },
              return_3y_pct: { p25: 20.0, p50: 28.4, p75: 40.0, p90: 50.0 },
            },
          },
        },
        rank_history: emptyDataEnvelope(),
        health: emptyDataEnvelope(),
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<PerformanceSection head={HEAD} isin={ISIN} />);

    // "This fund" row reuses head.return1yPct/3yPct/5yPct — the 8-col grid
    // above renders the SAME values (split across text nodes via ReturnValue),
    // so each also matches there; getAllByText tolerates both occurrences.
    expect(screen.getAllByText('+12.3%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('+45.6%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('+78.9%').length).toBeGreaterThan(0);

    // "Benchmark" row from the mocked /mf/benchmark/{key}/returns hook.
    expect(screen.getByText('+10.0%')).toBeInTheDocument();
    expect(screen.getByText('+30.0%')).toBeInTheDocument();

    // "Category avg" row from fund.analytics.category_percentiles p50.
    expect(screen.getByText('+9.5%')).toBeInTheDocument();
    expect(screen.getByText('+28.4%')).toBeInTheDocument();

    expect(screen.getAllByText('This fund').length).toBeGreaterThan(0); // row label (+ chart legend)
    expect(screen.getByText('Benchmark')).toBeInTheDocument();
    expect(screen.getByText('Category avg')).toBeInTheDocument();

    // No PreviewBadge on the default (Returns) tab now that it's real data.
    expect(screen.queryByText('Preview')).not.toBeInTheDocument();
  });

  it('shows "—" for cells with no real basis (5Y benchmark, 5Y/Launch category avg)', () => {
    mockUseFundNav.mockReturnValue({ data: undefined, isLoading: false });
    mockUseFundSip.mockReturnValue({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() });
    mockUseBenchmarkSeries.mockReturnValue({ data: undefined });
    mockUseBenchmarkReturns.mockReturnValue({
      data: {
        benchmark: 'nifty100',
        display_name: 'Nifty 100',
        disclosure: 'Nifty 100 · price index, excludes dividends',
        return_1y_pct: 10.0,
        return_3y_pct: null,
        return_5y_pct: null,
        as_of: '2026-06-30',
      },
    });
    mockUseFundAnalytics.mockReturnValue({
      data: {
        analytics: { status: 'empty', data: null },
        rank_history: emptyDataEnvelope(),
        health: emptyDataEnvelope(),
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<PerformanceSection head={{ ...HEAD, return3yPct: null, return5yPct: null }} isin={ISIN} />);

    // Multiple honest "—" cells across the table (Launch column always, plus
    // every field with no served basis) — assert at least one is present.
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
});

describe('Compare tab (Phase 4c pt4) — fund vs benchmark vs category', () => {
  // Shared no-op mocks for the OTHER Performance-Center tabs — the Returns tab
  // mounts first (default) before the click switches to Compare, so its hooks
  // must resolve without crashing even though these tests don't assert on it.
  function mockOtherPerfTabs() {
    mockUseFundNav.mockReturnValue({ data: undefined, isLoading: false });
    mockUseFundSip.mockReturnValue({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() });
    mockUseBenchmarkSeries.mockReturnValue({ data: undefined });
    mockUseBenchmarkReturns.mockReturnValue({ data: undefined });
    mockUseFundAnalytics.mockReturnValue({
      data: { analytics: emptyDataEnvelope(), rank_history: emptyDataEnvelope(), health: emptyDataEnvelope() },
      isLoading: false, isError: false, refetch: vi.fn(),
    });
  }

  const COMPARISON_ALL_PRESENT = {
    window: '5y' as const,
    anchor_date: '2024-01-01',
    series: {
      fund: [
        { d: '2024-01-01', v: 100.0 },
        { d: '2024-06-01', v: 112.5 },
      ],
      benchmark: {
        points: [
          { d: '2024-01-01', v: 100.0 },
          { d: '2024-06-01', v: 108.0 },
        ],
        label: 'Nifty 500 TRI',
        is_fallback: false,
      },
      category: {
        points: [
          { d: '2024-01-01', v: 100.0 },
          { d: '2024-06-01', v: 105.0 },
        ],
        reason: null,
      },
    },
    disclosure: 'Educational analysis only — not investment advice.',
    not_advice: 'NOT_ADVICE',
  };

  it('renders all three legend entries when all lines are present', () => {
    mockOtherPerfTabs();
    mockUseFundComparison.mockReturnValue({
      data: COMPARISON_ALL_PRESENT, isLoading: false, isFetching: false, isError: false, refetch: vi.fn(),
    });

    render(<PerformanceSection head={HEAD} isin={ISIN} />);
    fireEvent.click(screen.getByText('Compare'));

    expect(screen.getByText('This fund')).toBeInTheDocument();
    // 'Nifty 500 TRI' also appears as a <select> option (the dropdown) — getAllByText.
    expect(screen.getAllByText('Nifty 500 TRI').length).toBeGreaterThan(0);
    expect(screen.getByText('Category average')).toBeInTheDocument();
  });

  it('renders the honest fallback label verbatim when is_fallback is true', () => {
    mockOtherPerfTabs();
    const FALLBACK_LABEL = "Nifty 50 (broad market — not this scheme's benchmark)";
    mockUseFundComparison.mockReturnValue({
      data: {
        ...COMPARISON_ALL_PRESENT,
        series: {
          ...COMPARISON_ALL_PRESENT.series,
          benchmark: { points: COMPARISON_ALL_PRESENT.series.benchmark.points, label: FALLBACK_LABEL, is_fallback: true },
        },
      },
      isLoading: false, isFetching: false, isError: false, refetch: vi.fn(),
    });

    render(<PerformanceSection head={HEAD} isin={ISIN} />);
    fireEvent.click(screen.getByText('Compare'));

    expect(screen.getByText(FALLBACK_LABEL)).toBeInTheDocument();
  });

  it('renders the category reason line — never blank — when the category line is omitted', () => {
    mockOtherPerfTabs();
    const REASON = 'category average unavailable — cohort too thin';
    mockUseFundComparison.mockReturnValue({
      data: {
        ...COMPARISON_ALL_PRESENT,
        series: { ...COMPARISON_ALL_PRESENT.series, category: { points: null, reason: REASON } },
      },
      isLoading: false, isFetching: false, isError: false, refetch: vi.fn(),
    });

    render(<PerformanceSection head={HEAD} isin={ISIN} />);
    fireEvent.click(screen.getByText('Compare'));

    expect(screen.getByText(REASON)).toBeInTheDocument();
    expect(screen.queryByText('Category average')).not.toBeInTheDocument();
  });

  it('hover tooltip shows all three present lines', () => {
    mockOtherPerfTabs();
    mockUseFundComparison.mockReturnValue({
      data: COMPARISON_ALL_PRESENT, isLoading: false, isFetching: false, isError: false, refetch: vi.fn(),
    });
    // jsdom's getBoundingClientRect returns all-zero by default — the chart's
    // hover math needs a real width to convert clientX into a fraction.
    const rectSpy = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 680, height: 220, top: 0, left: 0, right: 680, bottom: 220, x: 0, y: 0, toJSON: () => {},
    } as DOMRect);

    render(<PerformanceSection head={HEAD} isin={ISIN} />);
    fireEvent.click(screen.getByText('Compare'));

    const chart = screen.getByRole('img', { name: /this fund versus its benchmark/i });
    fireEvent.mouseMove(chart, { clientX: 340 });

    expect(screen.getAllByText(/₹100 grew to ₹/)).toHaveLength(3);

    rectSpy.mockRestore();
  });

  it('renders no advisory verb anywhere in the Compare tab, in any data state', () => {
    // Kept as one space-joined string + .split(' ') so this guard file itself
    // does not trip ci_guards' own quoted-advisory-word scan (see
    // src/data/tooltip-copy-guard.test.ts for the same convention).
    const ADVISORY_VERBS =
      'buy sell hold invest reinvest divest avoid recommend rebalance book redeem should must ' +
      'consider diversify allocate trim increase reduce';
    const ADVISORY = new RegExp(String.raw`\b(${ADVISORY_VERBS.split(' ').join('|')})\b`, 'i');

    mockOtherPerfTabs();
    mockUseFundComparison.mockReturnValue({
      data: COMPARISON_ALL_PRESENT, isLoading: false, isFetching: false, isError: false, refetch: vi.fn(),
    });

    const { container } = render(<PerformanceSection head={HEAD} isin={ISIN} />);
    fireEvent.click(screen.getByText('Compare'));

    expect(ADVISORY.test(container.textContent ?? '')).toBe(false);
  });
});

describe('Risk Center advanced-ratio sentences (Fix 2)', () => {
  it('adds a Max Drawdown sentence when a category percentile band exists', () => {
    mockUseFundAnalytics.mockReturnValue({
      data: {
        analytics: {
          status: 'present',
          data: {
            sharpe_ratio: 1.2,
            sortino_ratio: 1.6,
            volatility_pct: 14.0,
            volatility_percentile: 40,
            max_drawdown_pct: -18.0,
            category_percentiles: {
              max_drawdown_pct: { p25: -25.0, p50: -18.0, p75: -12.0, p90: -8.0 },
            },
          },
        },
        health: {
          status: 'present',
          data: { lights: [{ name: 'Risk', light: 'y', note: 'Swings about as much as its category peers.' }], as_of: null },
        },
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<RiskCenterSection isin={ISIN} />);
    fireEvent.click(screen.getByText(/Advanced risk analytics/i));

    expect(screen.getByText('Its worst fall was about typical for its category.')).toBeInTheDocument();
    // Sharpe/Sortino must NEVER get a fabricated category-relative comparison
    // sentence anywhere in their own advanced-analytics row — no honest basis
    // is served for either metric today (unrelated to the generic Sharpe
    // "what this means" explainer paragraph elsewhere on the page).
    const sharpeRow = screen.getByText('Sharpe Ratio').closest('div.border-b');
    const sortinoRow = screen.getByText('Sortino Ratio').closest('div.border-b');
    expect(sharpeRow).not.toHaveTextContent(/category|peers/i);
    expect(sortinoRow).not.toHaveTextContent(/category|peers/i);
  });

  it('omits the Max Drawdown sentence when no category band is served (never fabricated)', () => {
    mockUseFundAnalytics.mockReturnValue({
      data: {
        analytics: {
          status: 'present',
          data: {
            sharpe_ratio: 1.2,
            sortino_ratio: 1.6,
            volatility_pct: 14.0,
            volatility_percentile: 40,
            max_drawdown_pct: -18.0,
            category_percentiles: {},
          },
        },
        health: { status: 'present', data: { lights: [], as_of: null } },
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<RiskCenterSection isin={ISIN} />);
    fireEvent.click(screen.getByText(/Advanced risk analytics/i));

    expect(screen.queryByText(/worst fall was (about typical|smaller|larger)/i)).not.toBeInTheDocument();
  });
});

describe('SnapshotSection (S9) — real KPI grid, null-safe', () => {
  it('renders real cells (NAV, expense, AUM, fund age, manager tenure, category rank)', () => {
    mockUseFundAnalytics.mockReturnValue({
      data: {
        analytics: { status: 'present', data: { tracking_error_pct: 0.21 } },
        rank_history: { status: 'empty', data: null, meta: { reason: null } },
        health: { status: 'empty', data: null, meta: { reason: null } },
      },
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    mockUseFundPeople.mockReturnValue({
      data: {
        people: { status: 'present', data: { managers: [{ name: 'A Sharma', start_date: '2021-01-01', tenure_years: 5.3 }], manager_changes_5y: 0 } },
        amc: { status: 'empty', data: null, meta: { reason: null } },
      },
      isLoading: false, isError: false, refetch: vi.fn(),
    });

    render(<SnapshotSection head={HEAD} isin={ISIN} />);

    expect(screen.getByText('₹120.00')).toBeInTheDocument(); // NAV
    expect(screen.getByText('0.75%')).toBeInTheDocument(); // Expense ratio
    expect(screen.getByText('0.21%')).toBeInTheDocument(); // Tracking error
    expect(screen.getByText('5.3 yrs')).toBeInTheDocument(); // Manager tenure
    expect(screen.getByText('#3 / 20')).toBeInTheDocument(); // Category rank
    expect(screen.getByText('None')).toBeInTheDocument(); // Lock-in (non-ELSS category)
    expect(screen.getByText('0.005%')).toBeInTheDocument(); // Stamp duty (statutory)
  });

  it('never fabricates a number — every source-blocked/missing field renders "—"', () => {
    mockUseFundAnalytics.mockReturnValue({
      data: { analytics: { status: 'empty', data: null, meta: { reason: null } }, rank_history: { status: 'empty', data: null, meta: { reason: null } }, health: { status: 'empty', data: null, meta: { reason: null } } },
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    mockUseFundPeople.mockReturnValue({
      data: { people: { status: 'empty', data: null, meta: { reason: null } }, amc: { status: 'empty', data: null, meta: { reason: null } } },
      isLoading: false, isError: false, refetch: vi.fn(),
    });

    const blankHead: FundHead = {
      ...HEAD,
      navLatest: null, navDate: null, navChangePct: null, expenseRatioPct: null,
      rank: null, total: null, launchDate: null, fundAumCr: null, fundAumAsOf: null,
      planOption: [], return1yPct: null, return3yPct: null, return5yPct: null,
    };

    render(<SnapshotSection head={blankHead} isin={ISIN} />);

    // Always-blocked cells (exit load, min SIP/lumpsum, turnover, riskometer) plus every
    // now-null real cell — at least several honest "—" cells, never a fabricated value.
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(8);
    expect(screen.getByText('Exit Load').parentElement).toBeInTheDocument();
    expect(screen.getByText('Riskometer').parentElement).toBeInTheDocument();
  });
});

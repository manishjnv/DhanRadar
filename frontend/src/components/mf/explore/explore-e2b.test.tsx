/**
 * E2b board wiring tests — Leaderboards, ConsistencyTable, LowCostTable, BeginnerPicks.
 * Fixtures from wire-captures/leaderboard-wire.json shapes.
 * Covers: board-present rows + LiveBadge, absent/undefined → EmptyState,
 * no fantasy labels/prose, no numeric composite score in DOM.
 */
import * as React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { LbBoard, LbFundRow, LbChampionRow } from '@/features/mf/types';

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) =>
    React.createElement('a', { href }, children),
}));

// ---------------------------------------------------------------------------
// Shared fixtures (wire-captured shapes)
// ---------------------------------------------------------------------------

const FUND_ROW: LbFundRow = {
  isin: 'INF00XX01BR2',
  fund_name_short: 'ITI Banking and Financial Services Fund',
  scheme_name: 'ITI Banking and Financial Services Fund -Regular Plan - Growth Option',
  amc_name: 'ITI Asset Management Limited',
  sebi_category: 'Equity Scheme - Sectoral/ Thematic',
  verb_label: 'on_track',
  confidence_band: 'medium',
  category_rank: 1,
  category_total: 943,
  rank_delta: 0,
  riskometer: 'Very High',
  return_1y_pct: 7.62,
  return_3y_pct: 39.28,
  return_5y_pct: null,
  expense_ratio_pct: 2.41,
  aum_crore: 351.47,
  sharpe_ratio: 0.31,
  max_drawdown_pct: 28.5,
  metric_value: 100.0,
  metric_unit: 'pct_rolling_positive',
  metric_category_avg: null,
};

const TER_ROW: LbFundRow = {
  isin: 'INF179KA1SC5',
  fund_name_short: 'HDFC Income Plus Arbitrage Active FOF',
  scheme_name: 'HDFC Income Plus Arbitrage Active FOF - Growth Option - Direct Plan',
  amc_name: 'HDFC Asset Management Company Limited',
  sebi_category: 'Other Scheme - Fund of Funds',
  verb_label: 'on_track',
  confidence_band: 'high',
  category_rank: 1,
  category_total: 50,
  rank_delta: 0,
  riskometer: 'Moderate',
  return_1y_pct: 5.99,
  return_3y_pct: 31.17,
  return_5y_pct: null,
  expense_ratio_pct: 0.02,
  aum_crore: 2045.46,
  sharpe_ratio: 1.05,
  max_drawdown_pct: 0.5,
  metric_value: 0.02,
  metric_unit: 'pct_ter',
  metric_category_avg: 0.42,
};

const EFF_ROW: LbFundRow = {
  isin: 'INF204K01YC4',
  fund_name_short: 'Nippon India Gold Savings Fund',
  scheme_name: 'Nippon India Gold Savings Fund - Direct Plan Growth Plan - Growth Option',
  amc_name: 'Nippon Life India Asset Management Limited',
  sebi_category: 'Other Scheme - Fund of Funds (Domestic)',
  verb_label: 'on_track',
  confidence_band: 'high',
  category_rank: 1,
  category_total: 20,
  rank_delta: 0,
  riskometer: 'High',
  return_1y_pct: 52.0,
  return_3y_pct: 153.38,
  return_5y_pct: null,
  expense_ratio_pct: 0.05,
  aum_crore: 6958.92,
  sharpe_ratio: 1.09,
  max_drawdown_pct: 12.0,
  metric_value: 3067.64,
  metric_unit: 'return_per_ter',
  metric_category_avg: null,
};

const BEGINNER_ROW: LbFundRow = {
  isin: 'INF03VN01696',
  fund_name_short: 'WhiteOak Capital Large Cap Fund',
  scheme_name: 'WhiteOak Capital Large Cap Fund Direct Plan Growth',
  amc_name: 'WhiteOak Capital Asset Management Limited',
  sebi_category: 'Equity Scheme - Large Cap Fund',
  verb_label: 'in_form',
  confidence_band: 'medium',
  category_rank: 16,
  category_total: 100,
  rank_delta: 0,
  riskometer: 'Very High',
  return_1y_pct: 3.51,
  return_3y_pct: 53.34,
  return_5y_pct: null,
  expense_ratio_pct: 0.42,
  aum_crore: 130.97,
  sharpe_ratio: 0.70,
  max_drawdown_pct: 14.0,
  metric_value: 9.04,
  metric_unit: 'pct_sip_xirr',
  metric_category_avg: 3.54,
};

const WINNER_ROW: LbFundRow = {
  isin: 'INF090I01KR8',
  fund_name_short: 'Franklin India Banking & PSU Debt Fund',
  scheme_name: 'Franklin India Banking & PSU Debt Fund - Direct - Growth',
  amc_name: 'Franklin Templeton Asset Management (India) Private Limited',
  sebi_category: 'Debt Scheme - Banking and PSU Fund',
  verb_label: 'in_form',
  confidence_band: 'medium',
  category_rank: 1,
  category_total: 178,
  rank_delta: 0,
  riskometer: 'Low to Moderate',
  return_1y_pct: 6.64,
  return_3y_pct: 24.63,
  return_5y_pct: 36.77,
  expense_ratio_pct: 0.21,
  aum_crore: 231.28,
  sharpe_ratio: 1.42,
  max_drawdown_pct: 1.03,
  metric_value: null,
  metric_unit: null,
  metric_category_avg: 11.17,
};

const CHAMPION_ROW: LbChampionRow = {
  category: 'Debt Scheme - Banking and PSU Fund',
  winner: WINNER_ROW,
  runner_up: null,
  why: 'Leads Debt Scheme - Banking and PSU Fund: trailing return computed from NAV history.',
};

// ---------------------------------------------------------------------------
// Leaderboards (section 04)
// ---------------------------------------------------------------------------
import { Leaderboards } from './Leaderboards';

describe('Leaderboards', () => {
  it('renders winner card when champions board is present', () => {
    const board: LbBoard<LbChampionRow> = { title: 'Category Champions', rows: [CHAMPION_ROW] };
    render(<Leaderboards champions={board} />);
    expect(screen.getByText('Franklin India Banking & PSU Debt Fund')).toBeTruthy();
    expect(screen.getAllByText(/Banking and PSU Fund/i).length).toBeGreaterThan(0);
  });

  it('renders row.why text', () => {
    const board: LbBoard<LbChampionRow> = { title: 'Category Champions', rows: [CHAMPION_ROW] };
    render(<Leaderboards champions={board} />);
    expect(screen.getByText(/trailing return computed from NAV history/i)).toBeTruthy();
  });

  it('renders honest #1 chip', () => {
    const board: LbBoard<LbChampionRow> = { title: 'Category Champions', rows: [CHAMPION_ROW] };
    render(<Leaderboards champions={board} />);
    expect(screen.getByText('#1')).toBeTruthy();
  });

  it('renders View all link to /mf/leaderboard', () => {
    const board: LbBoard<LbChampionRow> = { title: 'Category Champions', rows: [CHAMPION_ROW] };
    render(<Leaderboards champions={board} />);
    const link = screen.getByText(/view all/i).closest('a');
    expect(link?.getAttribute('href')).toBe('/mf/leaderboard');
  });

  it('slices to 12 rows at most', () => {
    const manyRows: LbChampionRow[] = Array.from({ length: 20 }, (_, i) => ({
      ...CHAMPION_ROW,
      category: `Category ${i}`,
      winner: { ...WINNER_ROW, isin: `INF000${i}`, fund_name_short: `Fund ${i}`, category_rank: 1 },
    }));
    const board: LbBoard<LbChampionRow> = { title: 'Champions', rows: manyRows };
    render(<Leaderboards champions={board} />);
    expect(screen.getAllByText('#1').length).toBe(12);
  });

  it('renders EmptyState when champions board is absent', () => {
    render(<Leaderboards champions={undefined} />);
    expect(screen.getByText(/category leaderboards not available/i)).toBeTruthy();
    expect(screen.getByText(/refreshed nightly/i)).toBeTruthy();
  });

  it('does NOT render any per-fund numeric composite score', () => {
    const board: LbBoard<LbChampionRow> = { title: 'Champions', rows: [CHAMPION_ROW] };
    const { container } = render(<Leaderboards champions={board} />);
    expect(container.textContent).not.toMatch(/score\s*:/i);
    expect(container.textContent).not.toMatch(/\b\d{2,3}\b.*percentile/i);
  });
});

// ---------------------------------------------------------------------------
// ConsistencyTable (section 08)
// ---------------------------------------------------------------------------
import { ConsistencyTable } from './LeaderTables';

describe('ConsistencyTable', () => {
  it('renders fund name and consistency word band when board present', () => {
    const board: LbBoard<LbFundRow> = { title: 'Consistency', rows: [FUND_ROW] };
    render(<ConsistencyTable sipConsistency={board} />);
    expect(screen.getByText('ITI Banking and Financial Services Fund')).toBeTruthy();
    // metric_value=100 → 'Strong'
    expect(screen.getByText('Strong')).toBeTruthy();
  });

  it('renders 1Y and 3Y returns', () => {
    const board: LbBoard<LbFundRow> = { title: 'Consistency', rows: [FUND_ROW] };
    render(<ConsistencyTable sipConsistency={board} />);
    expect(screen.getByText('7.6%')).toBeTruthy();
    expect(screen.getByText('39.3%')).toBeTruthy();
  });

  it('renders label+confidence band via LabelChip', () => {
    const board: LbBoard<LbFundRow> = { title: 'Consistency', rows: [FUND_ROW] };
    render(<ConsistencyTable sipConsistency={board} />);
    expect(screen.getByText(/on track/i)).toBeTruthy();
  });

  it('renders EmptyState when board is absent', () => {
    render(<ConsistencyTable sipConsistency={undefined} />);
    expect(screen.getByText(/consistency data not available/i)).toBeTruthy();
    expect(screen.getByText(/refreshed nightly/i)).toBeTruthy();
  });

  it('does NOT render fantasy columns (yrs beat cat, rank stability, persistence, mgr changes)', () => {
    const board: LbBoard<LbFundRow> = { title: 'Consistency', rows: [FUND_ROW] };
    const { container } = render(<ConsistencyTable sipConsistency={board} />);
    expect(container.textContent).not.toMatch(/yrs beat cat/i);
    expect(container.textContent).not.toMatch(/rank stability/i);
    expect(container.textContent).not.toMatch(/persistence/i);
    expect(container.textContent).not.toMatch(/mgr changes/i);
  });

  it('renders optional three_lens block when board present', () => {
    const mainBoard: LbBoard<LbFundRow> = { title: 'Consistency', rows: [FUND_ROW] };
    const lensBoard: LbBoard<LbFundRow> = {
      title: 'Three Lens',
      rows: [{ ...FUND_ROW, fund_name_short: 'Lens Fund A', isin: 'LENSA001' }],
    };
    render(<ConsistencyTable sipConsistency={mainBoard} threeLens={lensBoard} />);
    expect(screen.getByText(/strong on all three lenses/i)).toBeTruthy();
    expect(screen.getByText('Lens Fund A')).toBeTruthy();
  });

  it('does NOT render three_lens block when absent', () => {
    const board: LbBoard<LbFundRow> = { title: 'Consistency', rows: [FUND_ROW] };
    render(<ConsistencyTable sipConsistency={board} threeLens={undefined} />);
    expect(screen.queryByText(/strong on all three lenses/i)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// LowCostTable (section 09)
// ---------------------------------------------------------------------------
import { LowCostTable } from './LeaderTables';

describe('LowCostTable', () => {
  it('renders value_ter rows with TER and cat avg TER', () => {
    const terBoard: LbBoard<LbFundRow> = { title: 'Lowest TER', rows: [TER_ROW] };
    render(<LowCostTable valueTer={terBoard} valueEfficiency={undefined} />);
    expect(screen.getByText('HDFC Income Plus Arbitrage Active FOF')).toBeTruthy();
    expect(screen.getByText(/lowest expense ratio/i)).toBeTruthy();
    // TER 0.02% and cat avg 0.42%
    expect(screen.getByText('0.02%')).toBeTruthy();
    expect(screen.getByText('0.42%')).toBeTruthy();
  });

  it('renders value_efficiency rows with return-per-cost', () => {
    const effBoard: LbBoard<LbFundRow> = { title: 'Efficiency', rows: [EFF_ROW] };
    render(<LowCostTable valueTer={undefined} valueEfficiency={effBoard} />);
    expect(screen.getByText('Nippon India Gold Savings Fund')).toBeTruthy();
    expect(screen.getByText(/best return efficiency/i)).toBeTruthy();
    // metric_value=3067.64 → metricVal toFixed(0) rounds to '3068×'
    expect(screen.getByText(/306[78]\u00d7/)).toBeTruthy();
  });

  it('renders EmptyState when both boards absent', () => {
    render(<LowCostTable valueTer={undefined} valueEfficiency={undefined} />);
    expect(screen.getByText(/low-cost data not available/i)).toBeTruthy();
    expect(screen.getByText(/refreshed nightly/i)).toBeTruthy();
  });

  it('does NOT render fee15y or perf-retained columns', () => {
    const terBoard: LbBoard<LbFundRow> = { title: 'Lowest TER', rows: [TER_ROW] };
    const effBoard: LbBoard<LbFundRow> = { title: 'Efficiency', rows: [EFF_ROW] };
    const { container } = render(<LowCostTable valueTer={terBoard} valueEfficiency={effBoard} />);
    expect(container.textContent).not.toMatch(/15y fee/i);
    expect(container.textContent).not.toMatch(/perf.*retained/i);
    expect(container.textContent).not.toMatch(/₹10L/i);
  });
});

// ---------------------------------------------------------------------------
// BeginnerPicks (section 10 — "Steady SIP Starters")
// ---------------------------------------------------------------------------
import { BeginnerPicks } from './BeginnerPicks';

describe('BeginnerPicks', () => {
  it('renders fund name and riskometer from sip_beginner board', () => {
    const board: LbBoard<LbFundRow> = { title: 'SIP Beginner', rows: [BEGINNER_ROW] };
    render(<BeginnerPicks sipBeginner={board} />);
    expect(screen.getByText('WhiteOak Capital Large Cap Fund')).toBeTruthy();
    expect(screen.getByText('Very High')).toBeTruthy();
  });

  it('renders 3Y SIP XIRR and category average', () => {
    const board: LbBoard<LbFundRow> = { title: 'SIP Beginner', rows: [BEGINNER_ROW] };
    render(<BeginnerPicks sipBeginner={board} />);
    expect(screen.getByText('9.0%')).toBeTruthy();
    expect(screen.getByText(/cat avg 3\.5%/i)).toBeTruthy();
  });

  it('renders label+confidence band', () => {
    const board: LbBoard<LbFundRow> = { title: 'SIP Beginner', rows: [BEGINNER_ROW] };
    render(<BeginnerPicks sipBeginner={board} />);
    expect(screen.getByText(/in form/i)).toBeTruthy();
  });

  it('renders the D4 published rule at section level', () => {
    const board: LbBoard<LbFundRow> = { title: 'SIP Beginner', rows: [BEGINNER_ROW] };
    render(<BeginnerPicks sipBeginner={board} />);
    expect(screen.getByText(/D4 published criteria/i)).toBeTruthy();
  });

  it('renders EmptyState when board is absent', () => {
    render(<BeginnerPicks sipBeginner={undefined} />);
    expect(screen.getByText(/steady sip starters not available/i)).toBeTruthy();
    expect(screen.getByText(/refreshed nightly/i)).toBeTruthy();
  });

  it('does NOT render per-fund suitability prose (often suits / less suited)', () => {
    const board: LbBoard<LbFundRow> = { title: 'SIP Beginner', rows: [BEGINNER_ROW] };
    const { container } = render(<BeginnerPicks sipBeginner={board} />);
    expect(container.textContent).not.toMatch(/often suits/i);
    expect(container.textContent).not.toMatch(/less suited/i);
  });

  it('does NOT render any numeric composite score in DOM', () => {
    const board: LbBoard<LbFundRow> = { title: 'SIP Beginner', rows: [BEGINNER_ROW] };
    const { container } = render(<BeginnerPicks sipBeginner={board} />);
    expect(container.textContent).not.toMatch(/\bscore\b.*\d{2,}/i);
  });
});

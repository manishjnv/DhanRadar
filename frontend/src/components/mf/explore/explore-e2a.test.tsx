/**
 * E2a board plumbing tests — AiFeed, Momentum, FundFlowSection, SpotlightSignals.
 * Fixtures from wire-captures/leaderboard-wire.json shapes.
 * Covers: board-present rows, absent board EmptyState, boards===undefined endpoint-down path.
 */
import * as React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { LbBoard, LbFundRow, LbInsightRow, LbCategoryInflowRow, LbLabelUpgradeRow } from '@/features/mf/types';

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) =>
    React.createElement('a', { href }, children),
}));

// ---------------------------------------------------------------------------
// Shared fixtures (wire-captured shapes)
// ---------------------------------------------------------------------------

const FUND_ROW: LbFundRow = {
  isin: 'INF209K01P49',
  fund_name_short: 'Aditya Birla Sun Life Digital India Fund',
  scheme_name: 'Aditya Birla Sun Life Digital India Fund -DIRECT - IDCW',
  amc_name: 'Aditya Birla Sun Life AMC Limited',
  sebi_category: 'Equity Scheme - Sectoral/ Thematic',
  verb_label: 'off_track',
  confidence_band: 'medium',
  category_rank: 899,
  category_total: 943,
  rank_delta: 12,
  riskometer: 'Very High',
  return_1y_pct: -8.88,
  return_3y_pct: 0.36,
  return_5y_pct: -6.97,
  expense_ratio_pct: 2.11,
  aum_crore: 46.55,
  sharpe_ratio: -0.22,
  max_drawdown_pct: 34.93,
  metric_value: 12,
  metric_unit: 'rank_delta',
};

const DOWN_FUND_ROW: LbFundRow = {
  isin: 'INF200KB1787',
  fund_name_short: 'SBI Nifty200 Quality 30 Index Fund',
  scheme_name: 'SBI Nifty200 Quality 30 Index Fund-Regular Plan- Growth',
  amc_name: 'SBI Funds Management Limited',
  sebi_category: 'Other Scheme - Index Funds',
  verb_label: 'off_track',
  confidence_band: 'medium',
  category_rank: 996,
  category_total: 1342,
  rank_delta: -67,
  riskometer: 'Very High',
  return_1y_pct: 1.51,
  return_3y_pct: null,
  return_5y_pct: null,
  expense_ratio_pct: 0.82,
  aum_crore: 313.53,
  sharpe_ratio: -0.47,
  max_drawdown_pct: 15.88,
  metric_value: -67,
  metric_unit: 'rank_delta',
};

const AUM_GROWTH_ROW: LbFundRow = {
  isin: 'INF760K01175',
  fund_name_short: 'CANARA ROBECO LARGE AND MID CAP FUND',
  scheme_name: 'CANARA ROBECO LARGE AND MID CAP FUND - REGULAR PLAN - IDCW',
  amc_name: 'Canara Robeco Asset Management Company Limited',
  sebi_category: 'Equity Scheme - Large & Mid Cap Fund',
  verb_label: 'off_track',
  confidence_band: 'medium',
  category_rank: 137,
  category_total: 145,
  rank_delta: 0,
  riskometer: 'Very High',
  return_1y_pct: -3.82,
  return_3y_pct: 25.90,
  return_5y_pct: 34.36,
  expense_ratio_pct: 2.34,
  aum_crore: 25251.41,
  sharpe_ratio: 0.14,
  max_drawdown_pct: 26.02,
  metric_value: 18617.23,
  metric_unit: 'pct_mom_aum',
};

const INSIGHT_ROW: LbInsightRow = {
  text: 'The rank movers board shows that **LIC MF Conservative Hybrid Fund** has climbed.',
  links: [{ name: 'LIC MF Conservative Hybrid Fund', isin: 'INF767K01816' }],
};

const INFLOW_ROW: LbCategoryInflowRow = {
  category: 'Arbitrage Fund',
  net_flow_cr: 5697.9,
  period_month: '2026-05-01',
};

const SPOTLIGHT_ROW: LbFundRow = {
  ...FUND_ROW,
  isin: 'INF090I01IX0',
  fund_name_short: 'Franklin Asian Equity Fund',
  scheme_name: 'Franklin Asian Equity Fund - Direct - IDCW',
  metric_value: 3,
  metric_unit: 'boards',
};

const UPGRADE_ROW: LbLabelUpgradeRow = {
  ...FUND_ROW,
  isin: 'INF111X01234',
  fund_name_short: 'Test Upgrade Fund',
  scheme_name: 'Test Upgrade Fund - Direct - Growth',
  label_from: 'off_track',
  label_to: 'on_track',
};

// ---------------------------------------------------------------------------
// AiFeed
// ---------------------------------------------------------------------------
import { AiFeed } from './AiFeed';

describe('AiFeed', () => {
  it('renders rows when board is present (board-present + LiveBadge path)', () => {
    const board: LbBoard<LbInsightRow> = { title: 'AI Insights', rows: [INSIGHT_ROW] };
    render(<AiFeed board={board} />);
    expect(screen.getByText(/rank movers board/i)).toBeTruthy();
    // Name appears in bold span and in the link chip
    expect(screen.getAllByText('LIC MF Conservative Hybrid Fund').length).toBeGreaterThan(0);
  });

  it('renders EmptyState when board is absent', () => {
    render(<AiFeed board={undefined} />);
    expect(screen.getByText(/insights not available/i)).toBeTruthy();
  });

  it('renders EmptyState when boards===undefined (endpoint down)', () => {
    // boards===undefined: board prop evaluates to undefined via boards?.ai_insights
    render(<AiFeed board={undefined} />);
    expect(screen.getByText(/refreshed nightly/i)).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Momentum
// ---------------------------------------------------------------------------
import { Momentum } from './Momentum';

describe('Momentum', () => {
  it('renders climbing rows when moversUp board is present', () => {
    const moversUp: LbBoard<LbFundRow> = { title: 'Movers Up', rows: [FUND_ROW] };
    render(<Momentum moversUp={moversUp} moversDown={undefined} />);
    expect(screen.getByText('Aditya Birla Sun Life Digital India Fund')).toBeTruthy();
    expect(screen.getByText(/climbing rankings/i)).toBeTruthy();
    expect(screen.getByText(/since last ranking refresh/i)).toBeTruthy();
  });

  it('renders falling rows when moversDown board is present', () => {
    const moversDown: LbBoard<LbFundRow> = { title: 'Movers Down', rows: [DOWN_FUND_ROW] };
    render(<Momentum moversUp={undefined} moversDown={moversDown} />);
    expect(screen.getByText('SBI Nifty200 Quality 30 Index Fund')).toBeTruthy();
    expect(screen.getByText(/falling rankings/i)).toBeTruthy();
  });

  it('renders EmptyState when both boards absent', () => {
    render(<Momentum moversUp={undefined} moversDown={undefined} />);
    expect(screen.getByText(/momentum data not available/i)).toBeTruthy();
  });

  it('renders EmptyState when boards===undefined (endpoint down)', () => {
    // simulate boards?.movers_up → undefined, boards?.movers_down → undefined
    render(<Momentum moversUp={undefined} moversDown={undefined} />);
    expect(screen.getByText(/refreshed nightly/i)).toBeTruthy();
  });

  it('does NOT render time-range tabs (tabs deleted per E2a spec)', () => {
    const moversUp: LbBoard<LbFundRow> = { title: 'Movers Up', rows: [FUND_ROW] };
    render(<Momentum moversUp={moversUp} moversDown={undefined} />);
    expect(screen.queryByText('Last 30 Days')).toBeNull();
    expect(screen.queryByText('90 Days')).toBeNull();
    expect(screen.queryByText('1 Year')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// FundFlowSection
// ---------------------------------------------------------------------------
import { FundFlowSection } from './FundFlowSection';

describe('FundFlowSection', () => {
  it('renders category inflows when board is present', () => {
    const board: LbBoard<LbCategoryInflowRow> = { title: 'Category Inflows', rows: [INFLOW_ROW] };
    render(<FundFlowSection categoryInflows={board} aumGrowth={undefined} />);
    // Should show category name (shortened)
    expect(screen.getByText(/arbitrage/i)).toBeTruthy();
    // Method note must be present
    expect(screen.getByText(/AMFI category-level/i)).toBeTruthy();
  });

  it('renders AUM growth when board is present', () => {
    const board: LbBoard<LbFundRow> = { title: 'AUM Growth', rows: [AUM_GROWTH_ROW] };
    render(<FundFlowSection categoryInflows={undefined} aumGrowth={board} />);
    expect(screen.getByText('CANARA ROBECO LARGE AND MID CAP FUND')).toBeTruthy();
  });

  it('renders EmptyState when both boards absent', () => {
    render(<FundFlowSection categoryInflows={undefined} aumGrowth={undefined} />);
    expect(screen.getByText(/fund flow data not available/i)).toBeTruthy();
  });

  it('renders EmptyState when boards===undefined (endpoint down)', () => {
    render(<FundFlowSection categoryInflows={undefined} aumGrowth={undefined} />);
    expect(screen.getByText(/refreshed nightly/i)).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// SpotlightSignals
// ---------------------------------------------------------------------------
import { SpotlightSignals } from './SpotlightSignals';

describe('SpotlightSignals', () => {
  it('renders ai_spotlight rows when board is present', () => {
    const board: LbBoard<LbFundRow> = { title: 'AI Spotlight', rows: [SPOTLIGHT_ROW] };
    render(<SpotlightSignals aiSpotlight={board} />);
    expect(screen.getByText('Franklin Asian Equity Fund')).toBeTruthy();
    expect(screen.getByText('AI Spotlight')).toBeTruthy();
  });

  it('renders label_upgrades with educational label words (no advisory verbs)', () => {
    const board: LbBoard<LbLabelUpgradeRow> = { title: 'Label Upgrades', rows: [UPGRADE_ROW] };
    render(<SpotlightSignals labelUpgrades={board} />);
    expect(screen.getByText('Test Upgrade Fund')).toBeTruthy();
    // The upgrade lane should be present and not contain advisory verbs
    const container = screen.getByText('Test Upgrade Fund').closest('li');
    expect(container?.textContent).not.toMatch(/buy|sell|hold|caution|avoid/i);
    expect(screen.getByText('Label Upgrades')).toBeTruthy();
  });

  it('renders EmptyState when all boards absent', () => {
    render(<SpotlightSignals />);
    expect(screen.getByText(/spotlight data not available/i)).toBeTruthy();
  });

  it('renders EmptyState when boards===undefined (endpoint down)', () => {
    render(<SpotlightSignals aiSpotlight={undefined} hiddenGems={undefined} futureLeaders={undefined} labelUpgrades={undefined} />);
    expect(screen.getByText(/refreshed nightly/i)).toBeTruthy();
  });
});

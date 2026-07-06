/**
 * Fund Flow Intelligence (S14, Block 0.10 — category-level reframe) — vitest
 * tests confirming: (1) real category data renders with NO fabricated
 * inflow/outflow split, (2) the category label is shown and framed as
 * category-level (never "this fund's flows"), (3) the empty state renders
 * honestly when no category-flow rows exist yet.
 *
 * Holdings (S13, Block 0.11 — full-holdings depth) — vitest tests confirming
 * the show-first-N + "View all N holdings" expander (ADR-0033-B: the backend
 * already returns every disclosed row, no top-10-per-scheme cap; this is a
 * pure client-side render-size safeguard, no extra fetch).
 */

import * as React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { FundFlowSection, HoldingsSection } from './sectionsC';

const mockUseFundFlows = vi.fn();
const mockUseFundComposition = vi.fn();

vi.mock('@/features/mf/api', () => ({
  useFundComposition: (...args: unknown[]) => mockUseFundComposition(...args),
  useFundPeople: vi.fn(() => ({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() })),
  useFundFlows: (...args: unknown[]) => mockUseFundFlows(...args),
}));

const ISIN = 'INF200K01VT2';

function flowsEnvelope(
  points: Array<Record<string, unknown>>,
  scheme_category: string | null = 'Equity Scheme - Large Cap Fund',
) {
  return {
    status: 'present',
    data: {
      points,
      scheme_category,
      as_of_month: points.length ? points[points.length - 1].period_month : null,
    },
    meta: { reason: null },
  };
}

describe('FundFlowSection — category-level reframe (Block 0.10)', () => {
  it('renders real category data with the category label, never an Inflows/Outflows split', () => {
    mockUseFundFlows.mockReturnValue({
      data: flowsEnvelope([
        { period_month: '2026-05-01', net_flow_cr: 1250.5, net_aum_cr: 45000 },
        { period_month: '2026-06-01', net_flow_cr: -320.2, net_aum_cr: 44700 },
      ]),
      isLoading: false, isError: false, refetch: vi.fn(),
    });

    render(<FundFlowSection isin={ISIN} />);

    expect(screen.getByText('Equity Scheme - Large Cap Fund')).toBeInTheDocument();
    expect(screen.getByText(/-₹320 Cr/)).toBeInTheDocument();
    // Never the fund-level "Inflows"/"Outflows" split (that data doesn't exist).
    expect(screen.queryByText(/Inflows/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Outflows/i)).not.toBeInTheDocument();
    // Explicitly frames the data as category-level, not this fund's own flows.
    expect(screen.getByText(/not this fund alone/i)).toBeInTheDocument();
  });

  it('empty state (no category-flow rows yet) renders honestly, never fabricated data', () => {
    mockUseFundFlows.mockReturnValue({
      data: flowsEnvelope([], null),
      isLoading: false, isError: false, refetch: vi.fn(),
    });

    render(<FundFlowSection isin={ISIN} />);

    expect(screen.getByText(/isn.t published for this fund.s category yet/i)).toBeInTheDocument();
  });
});

function compositionEnvelope(holdingCount: number) {
  const holdings = Array.from({ length: holdingCount }, (_, i) => ({
    name: `Stock ${i + 1}`,
    sector: 'Financials',
    weight_pct: 10 - i * 0.05,
  }));
  return {
    status: 'present',
    data: {
      holdings,
      sectors: [],
      cap_mix: { large_pct: null, mid_pct: null, small_pct: null, unclassified_pct: null, basis: 'top_holdings_weight', as_of_period: null },
      as_of_month: '2026-06-01',
      coverage: { holdings_count: holdingCount, weight_covered_pct: 92.5 },
    },
    meta: { reason: null },
  };
}

describe('HoldingsSection — full-holdings depth expander (Block 0.11)', () => {
  it('a fund with <= 15 holdings renders every row with no expander button', () => {
    mockUseFundComposition.mockReturnValue({
      data: compositionEnvelope(8), isLoading: false, isError: false, refetch: vi.fn(),
    });

    render(<HoldingsSection isin="INF200K01VT2" />);

    expect(screen.getByText('Stock 1')).toBeInTheDocument();
    expect(screen.getByText('Stock 8')).toBeInTheDocument();
    expect(screen.queryByText(/View all/i)).not.toBeInTheDocument();
  });

  it('a fund with 300+ holdings shows only the first 15 with a "View all N holdings" expander, which reveals the rest on click', () => {
    mockUseFundComposition.mockReturnValue({
      data: compositionEnvelope(300), isLoading: false, isError: false, refetch: vi.fn(),
    });

    render(<HoldingsSection isin="INF200K01VT2" />);

    expect(screen.getByText('Stock 1')).toBeInTheDocument();
    expect(screen.getByText('Stock 15')).toBeInTheDocument();
    expect(screen.queryByText('Stock 16')).not.toBeInTheDocument();

    const expandBtn = screen.getByText('View all 300 holdings');
    fireEvent.click(expandBtn);

    expect(screen.getByText('Stock 300')).toBeInTheDocument();
  });
});

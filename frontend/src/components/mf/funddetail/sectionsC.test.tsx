/**
 * Fund Flow Intelligence (S14, Block 0.10 — category-level reframe) — vitest
 * tests confirming: (1) real category data renders with NO fabricated
 * inflow/outflow split, (2) the category label is shown and framed as
 * category-level (never "this fund's flows"), (3) the empty state renders
 * honestly when no category-flow rows exist yet.
 */

import * as React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { FundFlowSection } from './sectionsC';

const mockUseFundFlows = vi.fn();

vi.mock('@/features/mf/api', () => ({
  useFundComposition: vi.fn(() => ({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() })),
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

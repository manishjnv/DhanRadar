/**
 * My Investment (S5, P1) — vitest tests for the 3 UI states (FUND_DETAIL_DATA_ARCHITECTURE_PLAN
 * §5 row 5, §17 P1): anonymous/no-CAS, signed-in without this holding, signed-in with this holding.
 */

import * as React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { MyInvestmentSection } from './sectionsA';

const mockUsePortfolioHoldings = vi.fn();

vi.mock('@/features/portfolio/api', () => ({
  usePortfolioHoldings: (...args: unknown[]) => mockUsePortfolioHoldings(...args),
}));

const ISIN = 'INF200K01VT2';

function holdingsEnvelope(holdings: Array<Record<string, unknown>>) {
  return {
    status: 'present',
    data: { portfolio_id: 'pid-1', holdings },
    meta: { reason: null },
  };
}

describe('MyInvestmentSection — 3 UI states', () => {
  it('anonymous / no CAS → upload-CAS empty state (portfolioId empty, never hidden)', () => {
    mockUsePortfolioHoldings.mockReturnValue({
      data: undefined, isLoading: false, isError: false, refetch: vi.fn(),
    });
    render(<MyInvestmentSection portfolioId="" isin={ISIN} />);
    expect(screen.getByText(/upload your cas statement/i)).toBeInTheDocument();
  });

  it('signed-in without this holding → "you don\'t currently hold this fund" (never hidden)', () => {
    mockUsePortfolioHoldings.mockReturnValue({
      data: holdingsEnvelope([
        { isin: 'OTHERISIN0001', units: 5, invested_amount: 500, current_value: 600, current_nav: 12, data_state: 'ledger_backed' },
      ]),
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    render(<MyInvestmentSection portfolioId="pid-1" isin={ISIN} />);
    expect(screen.getByText(/don.t currently hold this fund/i)).toBeInTheDocument();
  });

  it('signed-in with this holding → renders the owner\'s real numbers', () => {
    mockUsePortfolioHoldings.mockReturnValue({
      data: holdingsEnvelope([
        {
          isin: ISIN, units: 100, invested_amount: 10000, current_value: 12000,
          current_nav: 120, xirr_pct: 18.5, day_change: 50, as_of: '2026-06-30',
          data_state: 'ledger_backed',
        },
      ]),
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    render(<MyInvestmentSection portfolioId="pid-1" isin={ISIN} />);
    expect(screen.getByText('₹12,000')).toBeInTheDocument();
    expect(screen.getByText(/18\.5%/)).toBeInTheDocument();
    expect(screen.queryByText(/upload your cas statement/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/don.t currently hold this fund/i)).not.toBeInTheDocument();
  });

  it('surfaces the ADR-0039 data-state tag for a non-default state', () => {
    mockUsePortfolioHoldings.mockReturnValue({
      data: holdingsEnvelope([
        {
          isin: ISIN, units: 100, invested_amount: 10000, current_value: 10000,
          current_nav: null, xirr_pct: null, day_change: null, as_of: '2026-06-30',
          data_state: 'unpriced',
        },
      ]),
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    render(<MyInvestmentSection portfolioId="pid-1" isin={ISIN} />);
    expect(screen.getByText(/price pending/i)).toBeInTheDocument();
  });
});

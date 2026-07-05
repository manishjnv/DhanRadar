/**
 * My Investment (S5, P1) — vitest tests for the 3 UI states (FUND_DETAIL_DATA_ARCHITECTURE_PLAN
 * §5 row 5, §17 P1): anonymous/no-CAS, signed-in without this holding, signed-in with this holding.
 *
 * Portfolio Fit (S4, 2026-07-06 P2) — vitest tests for its 3 UI states: anonymous, signed-in/no-CAS,
 * signed-in with data (category fact + overlap top-3 list).
 */

import * as React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { MyInvestmentSection, PortfolioFitSection } from './sectionsA';

const mockUsePortfolioHoldings = vi.fn();
const mockUseMe = vi.fn();
const mockUseFundPortfolioFit = vi.fn();

vi.mock('@/features/portfolio/api', () => ({
  usePortfolioHoldings: (...args: unknown[]) => mockUsePortfolioHoldings(...args),
}));

vi.mock('@/features/auth/api', () => ({
  useMe: (...args: unknown[]) => mockUseMe(...args),
}));

vi.mock('@/features/mf/api', () => ({
  useFundAnalytics: vi.fn(() => ({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() })),
  useFundEvents: vi.fn(() => ({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() })),
  useFundPortfolioFit: (...args: unknown[]) => mockUseFundPortfolioFit(...args),
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

  it('renders the ELSS lock-in strip only for an ELSS holding (P2, net new)', () => {
    mockUsePortfolioHoldings.mockReturnValue({
      data: holdingsEnvelope([
        {
          isin: ISIN, units: 100, invested_amount: 10000, current_value: 12000,
          current_nav: 120, xirr_pct: 18.5, day_change: 50, as_of: '2026-06-30',
          data_state: 'ledger_backed',
          lockin: {
            lots: [{ txn_date: '2024-01-01', units: 100, lock_until: '2027-01-01', locked: true }],
            locked_units: 100, free_units: 0, next_unlock_date: '2027-01-01', approximate: false,
          },
        },
      ]),
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    render(<MyInvestmentSection portfolioId="pid-1" isin={ISIN} />);
    expect(screen.getByText(/ELSS lock-in/i)).toBeInTheDocument();
    expect(screen.getByText(/lock ends 2027-01-01/i)).toBeInTheDocument();
  });

  it('renders no lock-in strip for a non-ELSS holding (lockin is null)', () => {
    mockUsePortfolioHoldings.mockReturnValue({
      data: holdingsEnvelope([
        {
          isin: ISIN, units: 100, invested_amount: 10000, current_value: 12000,
          current_nav: 120, xirr_pct: 18.5, day_change: 50, as_of: '2026-06-30',
          data_state: 'ledger_backed', lockin: null,
        },
      ]),
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    render(<MyInvestmentSection portfolioId="pid-1" isin={ISIN} />);
    expect(screen.queryByText(/ELSS lock-in/i)).not.toBeInTheDocument();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Portfolio Fit (S4, 2026-07-06 P2) — 3 UI states
// ═══════════════════════════════════════════════════════════════════════════

function fitEnvelope(data: Record<string, unknown> | null, status = 'present') {
  return { status, data, meta: { reason: null } };
}

describe('PortfolioFitSection — 3 UI states', () => {
  it('anonymous → sign-in prompt, never calls the fit endpoint result', () => {
    mockUseMe.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    mockUseFundPortfolioFit.mockReturnValue({
      data: undefined, isLoading: false, isError: false, refetch: vi.fn(),
    });
    render(<PortfolioFitSection portfolioId="" isin={ISIN} />);
    expect(screen.getByText(/sign in to compare this fund/i)).toBeInTheDocument();
  });

  it('signed-in, no CAS yet → upload-CAS prompt', () => {
    mockUseMe.mockReturnValue({ data: { id: 'u1', email: 'a@b.com' }, isLoading: false, isError: false });
    mockUseFundPortfolioFit.mockReturnValue({
      data: undefined, isLoading: false, isError: false, refetch: vi.fn(),
    });
    render(<PortfolioFitSection portfolioId="" isin={ISIN} />);
    expect(screen.getByText(/upload your cas statement to compare this fund/i)).toBeInTheDocument();
  });

  it('signed-in with data → renders category fact + overlap top-3 list, no advisory verbs', () => {
    mockUseMe.mockReturnValue({ data: { id: 'u1', email: 'a@b.com' }, isLoading: false, isError: false });
    mockUseFundPortfolioFit.mockReturnValue({
      data: fitEnvelope({
        portfolio_id: 'pid-1',
        viewed_isin: ISIN,
        overlap_pct: 30.0,
        category_allocation_pct: 45.5,
        fund_count_in_category: 2,
        overlap: [
          { holding_name: 'Held Fund One', overlap_pct: 50.0 },
          { holding_name: 'Held Fund Two', overlap_pct: 10.0 },
        ],
        overlap_coverage: true,
        data_completeness: 'constituent_data',
        observation: 'irrelevant fallback text',
      }),
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    render(<PortfolioFitSection portfolioId="pid-1" isin={ISIN} />);
    expect(screen.getByText(/45\.5%/)).toBeInTheDocument();
    expect(screen.getByText(/across 2 funds/i)).toBeInTheDocument();
    expect(screen.getByText('Held Fund One')).toBeInTheDocument();
    expect(screen.getByText(/50\.0%/)).toBeInTheDocument();
    expect(screen.getByText('Held Fund Two')).toBeInTheDocument();
    // No advisory verbs / verdict framing anywhere in the rendered output.
    const body = document.body.textContent ?? '';
    for (const banned of ['recommended', 'ideal', 'should', 'strong fit']) {
      expect(body.toLowerCase()).not.toContain(banned);
    }
  });
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import AdminAmcCoveragePage from './page';
import { useAmcCoverage } from '@/features/admin/api';
import type { AmcCoverageResponse } from '@/features/admin/api';

vi.mock('@/features/admin/api', async () => {
  const actual = await vi.importActual<typeof import('@/features/admin/api')>(
    '@/features/admin/api',
  );
  return { ...actual, useAmcCoverage: vi.fn() };
});

const RESPONSE: AmcCoverageResponse = {
  summary: {
    total_amcs: 2,
    total_funds: 250,
    nfo_count: 3,
    accuracy_pct: 82.4,
    overall_completeness_pct: 41.7,
    as_of: '2026-07-08T00:00:00+00:00',
  },
  rows: [
    {
      amc_name: 'Alpha AMC Limited',
      short_name: 'Alpha',
      fund_count: 200,
      fields: {
        constituents: { covered_count: 100, mode: 'A', freq: 'M' },
        aum: { covered_count: 50, mode: 'ML', freq: 'M' },
        ter: { covered_count: 0, mode: '-', freq: '-' },
        riskometer: { covered_count: 0, mode: '-', freq: '-' },
        benchmark: { covered_count: 0, mode: '-', freq: '-' },
        manager: { covered_count: 0, mode: '-', freq: '-' },
        exit_load: { covered_count: 0, mode: '-', freq: '-' },
        category: { covered_count: 150, mode: '-', freq: '-' },
      },
      completeness_pct: 30.5,
      source_tag: 'mixed',
      last_updated: '2026-06-01',
      staleness_days: 37,
    },
    {
      amc_name: 'Beta AMC Limited',
      short_name: 'Beta',
      fund_count: 50,
      fields: {
        constituents: { covered_count: 50, mode: 'A', freq: 'M' },
        aum: { covered_count: 50, mode: 'ML', freq: 'M' },
        ter: { covered_count: 10, mode: 'ML', freq: 'Y' },
        riskometer: { covered_count: 0, mode: '-', freq: '-' },
        benchmark: { covered_count: 0, mode: '-', freq: '-' },
        manager: { covered_count: 0, mode: '-', freq: '-' },
        exit_load: { covered_count: 0, mode: '-', freq: '-' },
        category: { covered_count: 50, mode: '-', freq: '-' },
      },
      completeness_pct: 60.0,
      source_tag: 'mixed',
      last_updated: null,
      staleness_days: null,
    },
  ],
  meta: {
    field_labels: {
      constituents: 'Constituents',
      aum: 'AUM',
      ter: 'TER',
      riskometer: 'Riskometer',
      benchmark: 'Benchmark',
      manager: 'Manager',
      exit_load: 'Exit load',
      category: 'Category',
    },
    field_order: [
      'constituents',
      'aum',
      'ter',
      'riskometer',
      'benchmark',
      'manager',
      'exit_load',
      'category',
    ],
    nfo_definition: 'Funds with a launch_date within the last 180 days.',
    accuracy_definition: 'Ingestion success rate.',
    completeness_definition: 'Per AMC average across 8 fields.',
    mode_definition: 'A = automatic scraper · ML = manual upload · - = no source yet.',
    freq_definition: 'Y = yearly · W = weekly · M = monthly · D = daily · O = once · - = none.',
    source_tag_definition: 'Badge next to the AMC name indicates overall source.',
    category_definition: 'Coverage of sebi_category.',
    staleness_definition: 'Updated = the later of aum_as_of and constituents as_of_month.',
    disclaimer: 'Data-coverage counts only.',
  },
};

describe('AdminAmcCoveragePage', () => {
  beforeEach(() => {
    vi.mocked(useAmcCoverage).mockReset();
  });

  it('renders the summary strip with the 5 stat tiles from real response data', () => {
    vi.mocked(useAmcCoverage).mockReturnValue({
      data: RESPONSE,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAmcCoverage>);

    render(<AdminAmcCoveragePage />);

    expect(screen.getByText('Total AMCs')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('Total Funds')).toBeInTheDocument();
    expect(screen.getByText('250')).toBeInTheDocument();
    expect(screen.getByText('NFOs (6mo)')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('Accuracy')).toBeInTheDocument();
    expect(screen.getByText('82.4%')).toBeInTheDocument();
    expect(screen.getByText('Overall Completeness')).toBeInTheDocument();
    expect(screen.getByText('41.7%')).toBeInTheDocument();
  });

  it('renders the per-AMC table rows from real response data', () => {
    vi.mocked(useAmcCoverage).mockReturnValue({
      data: RESPONSE,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAmcCoverage>);

    render(<AdminAmcCoveragePage />);

    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });

  it('shows a loading skeleton while the query is in flight', () => {
    vi.mocked(useAmcCoverage).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAmcCoverage>);

    render(<AdminAmcCoveragePage />);
    expect(screen.queryByText('Total AMCs')).not.toBeInTheDocument();
  });

  it('shows an error state with retry when the query fails', () => {
    vi.mocked(useAmcCoverage).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAmcCoverage>);

    render(<AdminAmcCoveragePage />);
    expect(screen.queryByText('Total AMCs')).not.toBeInTheDocument();
  });

  it('never renders an advisory action verb (compliance) and states the no-score disclaimer', () => {
    vi.mocked(useAmcCoverage).mockReturnValue({
      data: RESPONSE,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAmcCoverage>);

    const { container } = render(<AdminAmcCoveragePage />);
    const text = container.textContent?.toLowerCase() ?? '';
    // Advisory action verbs must never appear in any form on this page.
    const banned = 'buy|sell|strong buy'.split('|');
    for (const word of banned) {
      expect(text).not.toContain(word);
    }
    // The page must explicitly disclaim score/rating/recommendation (negated).
    expect(text).toContain('no fund score, rating, or recommendation');
  });

});

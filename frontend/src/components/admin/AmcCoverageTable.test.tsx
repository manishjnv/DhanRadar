import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AmcCoverageTable } from './AmcCoverageTable';
import type { AmcCoverageRow, CoverageField } from '@/features/admin/api';

const FIELD_ORDER: CoverageField[] = [
  'constituents',
  'aum',
  'ter',
  'riskometer',
  'benchmark',
  'manager',
  'exit_load',
];

const FIELD_LABELS: Record<CoverageField, string> = {
  constituents: 'Constituents',
  aum: 'AUM',
  ter: 'TER',
  riskometer: 'Riskometer',
  benchmark: 'Benchmark',
  manager: 'Manager',
  exit_load: 'Exit load',
};

function makeRow(overrides: Partial<AmcCoverageRow>): AmcCoverageRow {
  const emptyFields = Object.fromEntries(
    FIELD_ORDER.map((f) => [f, { covered_count: 0, mode: '-' as const, freq: '-' as const }]),
  ) as AmcCoverageRow['fields'];
  return {
    amc_name: 'Test AMC',
    short_name: 'Test',
    fund_count: 10,
    fields: emptyFields,
    completeness_pct: 0,
    ...overrides,
  };
}

const ROWS: AmcCoverageRow[] = [
  makeRow({ amc_name: 'Alpha AMC Limited', short_name: 'Alpha', fund_count: 500, completeness_pct: 20 }),
  makeRow({ amc_name: 'Beta AMC Limited', short_name: 'Beta', fund_count: 50, completeness_pct: 80 }),
  makeRow({ amc_name: 'Gamma AMC Limited', short_name: 'Gamma', fund_count: 200, completeness_pct: 50 }),
];

function firstColumnOrder(): string[] {
  const rows = screen.getAllByRole('rowheader');
  return rows.map((r) => r.textContent ?? '');
}

describe('AmcCoverageTable', () => {
  it('renders one row per AMC with short_name as the first column', () => {
    render(<AmcCoverageTable rows={ROWS} fieldOrder={FIELD_ORDER} fieldLabels={FIELD_LABELS} />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('Gamma')).toBeInTheDocument();
  });

  it('defaults to sorting by completeness (ascending)', () => {
    render(<AmcCoverageTable rows={ROWS} fieldOrder={FIELD_ORDER} fieldLabels={FIELD_LABELS} />);
    expect(firstColumnOrder()).toEqual(['Alpha', 'Gamma', 'Beta']); // 20 < 50 < 80
  });

  it('clicking the Funds header sorts by fund_count descending (first click)', () => {
    render(<AmcCoverageTable rows={ROWS} fieldOrder={FIELD_ORDER} fieldLabels={FIELD_LABELS} />);
    fireEvent.click(screen.getByText('Funds'));
    expect(firstColumnOrder()).toEqual(['Alpha', 'Gamma', 'Beta']); // 500 > 200 > 50
  });

  it('clicking the same header twice reverses sort direction', () => {
    render(<AmcCoverageTable rows={ROWS} fieldOrder={FIELD_ORDER} fieldLabels={FIELD_LABELS} />);
    fireEvent.click(screen.getByText('Funds'));
    fireEvent.click(screen.getByText('Funds'));
    expect(firstColumnOrder()).toEqual(['Beta', 'Gamma', 'Alpha']); // 50 < 200 < 500
  });

  it('sets aria-sort on the active column header only', () => {
    render(<AmcCoverageTable rows={ROWS} fieldOrder={FIELD_ORDER} fieldLabels={FIELD_LABELS} />);
    const amcHeader = screen.getByRole('columnheader', { name: /AMC/ });
    const fundsHeader = screen.getByRole('columnheader', { name: /Funds/ });

    expect(amcHeader).toHaveAttribute('aria-sort', 'none');
    // Default sort key is 'completeness' — its header should read ascending.
    const completeHeader = screen.getByRole('columnheader', { name: /Complete %/ });
    expect(completeHeader).toHaveAttribute('aria-sort', 'ascending');

    fireEvent.click(fundsHeader);
    expect(fundsHeader).toHaveAttribute('aria-sort', 'descending');
    expect(completeHeader).toHaveAttribute('aria-sort', 'none');
  });

  it('sorting by AMC name is alphabetical ascending', () => {
    render(<AmcCoverageTable rows={ROWS} fieldOrder={FIELD_ORDER} fieldLabels={FIELD_LABELS} />);
    fireEvent.click(screen.getByRole('columnheader', { name: /AMC/ }));
    expect(firstColumnOrder()).toEqual(['Alpha', 'Beta', 'Gamma']);
  });

  it('renders a mode·freq cell for a covered field and a plain count for an uncovered one', () => {
    const rows = [
      makeRow({
        amc_name: 'Covered AMC Limited',
        short_name: 'Covered',
        fields: {
          ...ROWS[0].fields,
          constituents: { covered_count: 334, mode: 'A', freq: 'M' },
        },
      }),
    ];
    render(<AmcCoverageTable rows={rows} fieldOrder={FIELD_ORDER} fieldLabels={FIELD_LABELS} />);
    expect(screen.getByText('A\u00B7M 334')).toBeInTheDocument();
  });

  it('renders the mode/frequency legend line', () => {
    render(<AmcCoverageTable rows={ROWS} fieldOrder={FIELD_ORDER} fieldLabels={FIELD_LABELS} />);
    expect(screen.getByText(/A=auto M=manual/)).toBeInTheDocument();
  });
});

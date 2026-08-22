/**
 * Batch A regression tests (audit 2026-08-22): no sample funds under a LIVE
 * badge — anonymous AI sections show a sign-in state, Similar Funds honours
 * its exclusion promise + one card per scheme, and live tables render the
 * REAL fund names as column headers.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { EduReadSection, AltsSection } from './sections';
import { CompareTable } from './ui';
import { FUNDS } from './sampleData';
import type { CompareAlternative } from '@/features/mf/types';

describe('Batch A — no sample funds under LIVE badges', () => {
  it('EduReadSection with needsAuth shows sign-in state, never sample funds', () => {
    render(<EduReadSection needsAuth items={undefined} />);
    expect(screen.getByText('Sign in to see this')).toBeInTheDocument();
    expect(screen.queryByText(/Bandhan/)).not.toBeInTheDocument();
  });

  it('AltsSection excludes compared isins and dedupes same-scheme variants', () => {
    const base = { amc_name: null, sebi_category: null, verb_label: null, confidence_band: null };
    const alts: CompareAlternative[] = [
      { ...base, isin: 'COMPARED00001', scheme_name: 'Compared Fund', fund_name_short: 'Compared Fund', return_1y_pct: null, return_3y_pct: null, expense_ratio_pct: null },
      { ...base, isin: 'TATA00000001', scheme_name: 'TATA SmallCap', fund_name_short: 'Tata Small Cap', return_1y_pct: 1, return_3y_pct: 2, expense_ratio_pct: 0.5 },
      { ...base, isin: 'TATA00000002', scheme_name: 'Tata Small Cap Fund', fund_name_short: 'Tata Small Cap', return_1y_pct: 1.1, return_3y_pct: 2.1, expense_ratio_pct: 0.6 },
    ];
    render(<AltsSection alternatives={alts} isins={['COMPARED00001', 'OTHER0000002']} />);
    expect(screen.queryByText('Compared Fund')).not.toBeInTheDocument();
    expect(screen.getAllByText('Tata Small Cap')).toHaveLength(1);
  });

  it('CompareTable headers come from the passed funds, not the 3 sample names', () => {
    const funds = [
      { ...FUNDS[0], key: 'IN0000000001', short: 'Kotak' },
      { ...FUNDS[1], key: 'IN0000000002', short: 'HSBC' },
    ];
    render(<CompareTable rows={[{ label: '1Y', vals: ['1%', '2%'] }]} funds={funds} />);
    expect(screen.getByText('Kotak')).toBeInTheDocument();
    expect(screen.getByText('HSBC')).toBeInTheDocument();
    expect(screen.queryByText('Quant')).not.toBeInTheDocument();
  });
});

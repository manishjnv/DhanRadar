/**
 * Regression test — RCA 2026-08-22: HoldingsSection crashed every live
 * comparison ("Cannot read properties of undefined (reading 'holdings')")
 * because the frontend type invented a `data` wrapper the backend never sends.
 * The composition fixtures here use the REAL wire shape captured from
 * GET /api/v1/mf/compare/bundle (flat {holdings, sectors, coverage,
 * as_of_month}) — never shape fixtures from the TypeScript type alone.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { HoldingsSection } from './sections';
import { FUNDS } from './sampleData';
import type { CompareCompositionFragment } from '@/features/mf/types';

const funds = [
  { ...FUNDS[0], key: 'INF174K01211', short: 'Kotak' },
  { ...FUNDS[1], key: 'INF740K01805', short: 'DSP' },
];

const compositions: Record<string, CompareCompositionFragment | null> = {
  // Real wire shape — flat, no `data` wrapper, no `no_data` key when data exists.
  INF174K01211: {
    holdings: [{ name: 'ASTER DM HEALTHCARE LTD', sector: 'Healthcare Services', weight_pct: 4.63 }],
    sectors: [{ name: 'Healthcare Services', weight_pct: 4.63 }],
    coverage: { holdings_count: 1, weight_covered_pct: 4.63 },
    as_of_month: '2026-06',
  },
  INF740K01805: { no_data: true },
};

describe('HoldingsSection (live wire shape)', () => {
  it('renders real holdings without crashing and EmptyState for no_data funds', () => {
    render(
      <HoldingsSection
        compositions={compositions}
        pairwiseOverlap={[]}
        funds={funds}
        isins={['INF174K01211', 'INF740K01805']}
      />,
    );
    expect(screen.getByText('ASTER DM HEALTHCARE LTD')).toBeInTheDocument();
    expect(screen.getByText(/Holdings unavailable/i)).toBeInTheDocument();
  });
});

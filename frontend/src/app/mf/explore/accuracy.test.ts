import { describe, expect, it } from 'vitest';
import { EXPLORE_CSV_HEADERS } from '@/features/mf/explorer-export';

describe('Fund Explorer CSV export contract', () => {
  it('contains factual fields only', () => {
    const headers = EXPLORE_CSV_HEADERS.join('|').toLowerCase();
    expect(headers).not.toMatch(/unified_score|score|factor_weights|fair_value/);
    expect(headers).not.toMatch(/buy|sell|hold|avoid/);
    expect(EXPLORE_CSV_HEADERS).toEqual(expect.arrayContaining([
      'TER%', 'AUM(Cr)', 'Risk', 'Sharpe', 'Drawdown%', 'Label', 'Band',
    ]));
  });
});
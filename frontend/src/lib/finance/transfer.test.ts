/**
 * Tests for the E4 transfer (STP) engine. Key invariant: at equal source/target
 * rates, money moved between funds is conserved — combined == a single untouched
 * fund grown at that rate.
 */
import { describe, it, expect } from 'vitest';
import { computeStp } from './transfer';

describe('computeStp', () => {
  it('conservation: equal rates → combined equals the untouched fund', () => {
    const r = computeStp({ sourceCorpus: 1000000, monthlyTransfer: 20000, sourceRatePct: 10, targetRatePct: 10, years: 3 });
    const untouched = 1000000 * Math.pow(1 + 0.10 / 12, 36);
    expect(Math.abs(r.combined - untouched)).toBeLessThan(1); // within ₹1
  });

  it('transfers move value from source into target', () => {
    const r = computeStp({ sourceCorpus: 1000000, monthlyTransfer: 25000, sourceRatePct: 6, targetRatePct: 12, years: 4 });
    expect(r.targetBuilt).toBeGreaterThan(0);
    expect(r.sourceLeft).toBeLessThan(1000000);
    expect(r.totalTransferred).toBeGreaterThan(0);
  });

  it('a large transfer drains the source within the horizon', () => {
    const r = computeStp({ sourceCorpus: 600000, monthlyTransfer: 50000, sourceRatePct: 6, targetRatePct: 12, years: 5 });
    expect(r.monthsToDrain).toBeGreaterThan(0);
    expect(r.sourceLeft).toBe(0);
  });

  it('NaN / negative inputs stay finite', () => {
    const r = computeStp({ sourceCorpus: NaN, monthlyTransfer: -1, sourceRatePct: -5, targetRatePct: NaN, years: -2 });
    for (const v of [r.targetBuilt, r.sourceLeft, r.combined, r.totalTransferred]) expect(Number.isFinite(v)).toBe(true);
  });
});

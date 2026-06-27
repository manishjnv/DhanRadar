import { describe, expect, it } from 'vitest';
import { tooltipFns } from './tooltipFns';

/**
 * §28.7 — a dynamic tooltip is score-free BY CONSTRUCTION (SafePoint carries no
 * score/weight/fairValue key). This asserts the contract so a future edit can't sneak a
 * bare 0–100 composite score into a tip. The user's OWN number rides in `ownValue` and is
 * #2-exempt, so we feed a SafePoint with NO ownValue and require zero digits in the output.
 */
describe('tooltipFns', () => {
  it('emit no bare numeric score when no user value is present', () => {
    const pt = { label: 'Equity' }; // no ownValue; no `score` field exists to interpolate
    for (const [id, fn] of Object.entries(tooltipFns)) {
      const out = fn(pt);
      expect(out, `${id} leaked a number`).not.toMatch(/\d/);
      expect(out.split(' ').length, `${id} over 12 words`).toBeLessThanOrEqual(12);
    }
  });

  it("show the user's own value verbatim (it is #2-exempt)", () => {
    expect(tooltipFns.allocation_donut({ label: 'Equity', ownValue: '68%' })).toBe(
      'Equity: 68% of your portfolio.',
    );
  });
});

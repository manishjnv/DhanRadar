/**
 * §28.7 tooltip copy guard — the DETERMINISTIC compliance gate over the data-driven help copy.
 *
 * Every STATIC help string (concepts.json `help_text` + components.json `tooltip`/`field_tooltips`) must
 * be ≤12 words (founder simple-words), carry NO advisory verb (#1), and NO bare number (#2 — the user's
 * own ₹/% appear only in the SafePoint-typed dynamic `tooltip_fn`). The dynamic fns are score-free BY
 * CONSTRUCTION (SafePoint has no score/weight/fairValue key); we also assert they interpolate only the
 * label + the user's own value, never a fabricated number.
 */
import { describe, expect, it } from 'vitest';

import { CONCEPTS, COMPONENTS } from './concepts.generated';
import type { SafePoint } from './envelope';
import { tooltipFns } from './tooltipFns';

// #1: advisory verbs (the SEBI boundary), kept as a space-string so THIS guard file does not trip
// ci_guards' own quoted-advisory-word scan. Word boundaries mean possession/past-tense (you invested,
// holding) does not trip — only the imperative forms do.
const ADVISORY_VERBS =
  'buy sell hold invest reinvest divest avoid recommend rebalance book redeem should must ' +
  'consider diversify allocate trim increase reduce';
const ADVISORY = new RegExp(String.raw`\b(${ADVISORY_VERBS.split(' ').join('|')})\b`, 'i');

const wordCount = (s: string) => s.trim().split(/\s+/).filter(Boolean).length;

interface Tip {
  where: string;
  text: string;
}

function staticTips(): Tip[] {
  const out: Tip[] = [];
  for (const c of CONCEPTS) {
    if (c.help_text) out.push({ where: `concept ${c.concept}.help_text`, text: c.help_text });
  }
  for (const c of COMPONENTS) {
    if (c.tooltip) out.push({ where: `component ${c.component}.tooltip`, text: c.tooltip });
    for (const [k, v] of Object.entries(c.field_tooltips ?? {})) {
      out.push({ where: `component ${c.component}.field_tooltips.${k}`, text: v });
    }
  }
  return out;
}

describe('§28.7 tooltip copy guard', () => {
  const tips = staticTips();

  it('there is copy to guard', () => {
    expect(tips.length).toBeGreaterThan(10);
  });

  it.each(tips)('$where — ≤12 words, non-advisory, no number', ({ where, text }) => {
    expect(wordCount(text), `>12 words (${where}): "${text}"`).toBeLessThanOrEqual(12);
    expect(ADVISORY.test(text), `advisory verb (${where}): "${text}"`).toBe(false);
    expect(/\d/.test(text), `bare number in a static tip (${where}): "${text}"`).toBe(false);
  });

  it('dynamic tooltip_fns interpolate only label + the user own value (no fabricated score)', () => {
    const pt: SafePoint = { label: 'Equity', ownValue: 'OWNVAL' }; // digit-free sentinel
    for (const [name, fn] of Object.entries(tooltipFns)) {
      const out = fn(pt);
      expect(out, `${name} dropped the user's own value`).toContain('OWNVAL');
      expect(/\d/.test(out), `${name} fabricated a number beyond ownValue: "${out}"`).toBe(false);
    }
  });
});

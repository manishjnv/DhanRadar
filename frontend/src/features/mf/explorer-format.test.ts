import { describe, it, expect } from 'vitest';
import { cleanSchemeName, formatCategoryLabel } from './explorer-format';

describe('cleanSchemeName', () => {
  it('strips the "- Regular Plan - Growth Option" suffix (the feedback example)', () => {
    expect(cleanSchemeName('ITI Banking & PSU Debt Fund - Regular Plan - Growth Option'))
      .toBe('ITI Banking & PSU Debt Fund');
  });

  it('strips "- Direct Plan - IDCW"', () => {
    expect(cleanSchemeName('HDFC Gilt Fund - Direct Plan - IDCW')).toBe('HDFC Gilt Fund');
  });

  it('strips a bare "- Growth" suffix', () => {
    expect(cleanSchemeName('Axis Small Cap Fund - Growth')).toBe('Axis Small Cap Fund');
  });

  it('leaves a name without a plan/option suffix untouched', () => {
    expect(cleanSchemeName('Parag Parikh Flexi Cap Fund')).toBe('Parag Parikh Flexi Cap Fund');
  });

  it('does NOT strip an internal hyphen that is part of the real name', () => {
    // No plan/option token after the hyphen → must be preserved.
    expect(cleanSchemeName('Mirae Asset Nifty 50 - Index')).toBe('Mirae Asset Nifty 50 - Index');
  });

  it('falls back to the original if stripping would empty the name', () => {
    // Degenerate input that is *only* a suffix → must not return an empty string.
    expect(cleanSchemeName('- Growth')).toBe('- Growth');
  });
});

describe('formatCategoryLabel', () => {
  it('replaces "and" with "&" and drops a trailing " Fund"', () => {
    expect(formatCategoryLabel('Banking and PSU Fund')).toBe('Banking & PSU');
  });

  it('drops a trailing " Fund" for simple categories', () => {
    expect(formatCategoryLabel('Small Cap Fund')).toBe('Small Cap');
  });

  it('preserves a mid-string "Fund" (only a trailing " Fund" is dropped)', () => {
    // No standalone "and" and no trailing " Fund" → returned unchanged.
    expect(formatCategoryLabel('Gilt Fund with 10 year constant duration'))
      .toBe('Gilt Fund with 10 year constant duration');
  });
});

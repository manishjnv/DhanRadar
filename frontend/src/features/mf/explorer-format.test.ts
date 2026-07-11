import { describe, it, expect } from 'vitest';
import {
  cleanSchemeName, formatCategoryLabel, shortenAmcName,
  fundDisplayTitle, fundVariantTags, optionDisplay,
} from './explorer-format';

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

  it('preserves a mid-string "Fund" but abbreviates "10 year" → "10Y"', () => {
    // No trailing " Fund" (so "Fund" is kept); "10 year" is shortened.
    expect(formatCategoryLabel('Gilt Fund with 10 year constant duration'))
      .toBe('Gilt Fund with 10Y constant duration');
  });
});

describe('fundDisplayTitle', () => {
  it('prefers the server-derived fund_name_short', () => {
    expect(fundDisplayTitle({
      scheme_name: 'SBI Banking & PSU Fund - Direct Plan - Daily Income Distribution cum Capital Withdrawal Option (IDCW)',
      fund_name_short: 'SBI Banking & PSU Fund',
    })).toBe('SBI Banking & PSU Fund');
  });

  it('falls back to cleanSchemeName when fund_name_short is null', () => {
    expect(fundDisplayTitle({
      scheme_name: 'Axis Small Cap Fund - Growth',
      fund_name_short: null,
    })).toBe('Axis Small Cap Fund');
  });
});

describe('fundVariantTags', () => {
  it('builds asset class + category + plan + option (the founder example)', () => {
    expect(fundVariantTags({
      scheme_name: 'x',
      sebi_category: 'Debt Scheme - Banking and PSU Fund',
      plan_type: 'direct',
      option_type: 'idcw',
      idcw_frequency: 'daily',
    })).toEqual(['Debt', 'Banking & PSU', 'Direct', 'IDCW · Daily']);
  });

  it('handles a category without the "Scheme -" prefix and growth option', () => {
    expect(fundVariantTags({
      scheme_name: 'x',
      sebi_category: 'Small Cap Fund',
      plan_type: 'regular',
      option_type: 'growth',
    })).toEqual(['Small Cap', 'Regular', 'Growth']);
  });

  it('returns [] when nothing is known (legacy rows)', () => {
    expect(fundVariantTags({ scheme_name: 'x' })).toEqual([]);
  });
});

describe('optionDisplay', () => {
  it('appends the IDCW payout frequency', () => {
    expect(optionDisplay({ scheme_name: 'x', option_type: 'idcw', idcw_frequency: 'monthly' }))
      .toBe('IDCW · Monthly');
  });

  it('ignores frequency for growth', () => {
    expect(optionDisplay({ scheme_name: 'x', option_type: 'growth', idcw_frequency: 'daily' }))
      .toBe('Growth');
  });
});

describe('shortenAmcName', () => {
  it('shortens "Asset Management Limited" → "AMC"', () => {
    expect(shortenAmcName('ITI Asset Management Limited')).toBe('ITI AMC');
  });

  it('shortens a bare "Asset Management" → "AMC"', () => {
    expect(shortenAmcName('WhiteOak Capital Asset Management')).toBe('WhiteOak Capital AMC');
  });

  it('shortens "Asset Management Company Private Limited" → "AMC"', () => {
    expect(shortenAmcName('Nippon Life India Asset Management Company Private Limited'))
      .toBe('Nippon Life India AMC');
  });

  it('leaves a name that already uses "AMC" unchanged', () => {
    expect(shortenAmcName('Aditya Birla Sun Life AMC')).toBe('Aditya Birla Sun Life AMC');
  });
});

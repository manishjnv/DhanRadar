import { describe, expect, it } from 'vitest';
import { fundDisplayName } from './fundDisplayName';

describe('fundDisplayName (E-3, display-only)', () => {
  it('abbreviates structural terms without a tag', () => {
    expect(fundDisplayName('Tata Silver Exchange Traded Fund')).toEqual({ name: 'Tata Silver ETF' });
    expect(fundDisplayName('SBI Silver ETF Fund of Fund')).toEqual({ name: 'SBI Silver ETF FoF' });
  });

  it('applies the fixed AMC brand map', () => {
    expect(fundDisplayName('ICICI Prudential Overnight Fund')).toEqual({ name: 'ICICI Pru Overnight Fund' });
    expect(fundDisplayName('Aditya Birla Sun Life Liquid Fund')).toEqual({ name: 'ABSL Liquid Fund' });
  });

  it('splits plan/variant qualifiers into the tag (the founder example)', () => {
    expect(
      fundDisplayName('ICICI Prudential Overnight fund - Direct Plan - Unclaimed IDCW Transitory Scheme'),
    ).toEqual({
      name: 'ICICI Pru Overnight fund',
      tag: 'Direct Plan · Unclaimed IDCW Transitory Scheme',
    });
  });

  it('keeps non-qualifier hyphen segments in the core name (Bharat Bond)', () => {
    expect(fundDisplayName('Bharat Bond FOF - April 2030')).toEqual({ name: 'Bharat Bond FOF - April 2030' });
  });

  it('moves side-pocket count parentheticals to the tag', () => {
    expect(
      fundDisplayName('Nippon India Conservative Hybrid Fund (Existing number of Segregated Portfolios - 1)'),
    ).toEqual({
      name: 'Nippon India Conservative Hybrid Fund',
      tag: 'Existing number of Segregated Portfolios - 1',
    });
  });

  it('never returns an empty name', () => {
    expect(fundDisplayName('Direct Plan - Growth Option').name).not.toBe('');
  });
});

import { shortenAmcName, categoryDisplayName } from './explorer-format';

describe('shortenAmcName (Phase H)', () => {
  it('collapses every legal-suffix family to AMC', () => {
    expect(shortenAmcName('HSBC Asset Management (India) Private Ltd.')).toBe('HSBC AMC');
    expect(shortenAmcName('quant Money Managers Limited')).toBe('quant AMC');
    expect(shortenAmcName('SBI Funds Management Limited')).toBe('SBI AMC');
    expect(shortenAmcName('Bank of India Investment Managers Private Limited')).toBe('Bank of India AMC');
    expect(shortenAmcName('ITI Asset Management Limited')).toBe('ITI AMC');
  });
  it('leaves already-clean names alone', () => {
    expect(shortenAmcName('Zerodha AMC')).toBe('Zerodha AMC');
  });
});

describe('categoryDisplayName (Phase H)', () => {
  it('drops Scheme/Fund and shortens conjunctions', () => {
    expect(categoryDisplayName('Equity Scheme - Flexi Cap Fund')).toBe('Equity · Flexi Cap');
    expect(categoryDisplayName('Debt Scheme - Banking and PSU Fund')).toBe('Debt · Banking & PSU');
    expect(categoryDisplayName('Equity Scheme - ELSS')).toBe('Equity · ELSS');
    expect(categoryDisplayName('Other Scheme - Index Funds')).toBe('Other · Index');
    expect(categoryDisplayName('Solution Oriented Scheme - Retirement Fund')).toBe('Solution · Retirement');
  });
});

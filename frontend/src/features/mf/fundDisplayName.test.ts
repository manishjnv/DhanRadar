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

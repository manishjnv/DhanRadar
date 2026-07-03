import { describe, it, expect } from 'vitest';
import { shortAmcName } from './format';

describe('shortAmcName', () => {
  it('strips "Asset Management Company Limited" down to the bare brand', () => {
    expect(shortAmcName('HDFC Asset Management Company Limited')).toBe('HDFC');
  });

  it('strips "Investment Managers" down to the bare brand', () => {
    expect(shortAmcName('DSP Investment Managers')).toBe('DSP');
  });

  it('keeps a multi-word brand recognizable', () => {
    expect(shortAmcName('ICICI Prudential Asset Management Company Ltd')).toBe('ICICI Prudential');
  });

  it('strips a bare "Asset Management" suffix', () => {
    expect(shortAmcName('WhiteOak Capital Asset Management')).toBe('WhiteOak Capital');
  });

  it('leaves an already-bare name unchanged', () => {
    expect(shortAmcName('Parag Parikh')).toBe('Parag Parikh');
  });

  it('falls back to the original name if stripping would empty it', () => {
    expect(shortAmcName('Asset Management Company Limited')).toBe('Asset Management Company Limited');
  });
});

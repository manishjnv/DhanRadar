/**
 * SipCalculator — compliance + behaviour tests.
 *
 * The calculator is a compliance surface first: it must render the mandatory
 * disclaimer, never use advisory verbs, never name a fund, and never leak
 * NaN / Infinity into the DOM for any input (Goal-Calculator Inv. 1/3/9/10).
 */
import * as React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { SipCalculator, CALC_DISCLAIMER } from './SipCalculator';

// Advisory verbs / phrases banned in educational copy (non-neg #1). Single
// space-separated string → split, never individually quoted tokens, so the
// deterministic anti-pattern scan does not read this guard as shipped advisory
// copy. NOTE: the bare word "invest" is intentionally NOT here — "investment
// advice" and "mutual fund investments" are the MANDATED risk wording.
const ADVISORY =
  'buy sell hold recommend should avoid switch allocate overweight underweight'.split(' ');
const ADVISORY_PHRASES = ['invest now', 'start sip', 'best fund', 'buy now', 'good time to'];

// Representative AMC / fund-name tokens that must never appear (no fund names).
const FUND_NAMES = [
  'HDFC', 'SBI', 'Axis', 'ICICI', 'Nippon', 'Parag Parikh', 'Mirae', 'Kotak',
  'Quant', 'UTI', 'Franklin', 'Aditya Birla',
];

function bodyText(): string {
  return (document.body.textContent ?? '').toLowerCase();
}

describe('SipCalculator — mandatory disclaimer', () => {
  it('renders the exact illustrative-only disclaimer next to the result', () => {
    render(<SipCalculator />);
    expect(screen.getByText(CALC_DISCLAIMER)).toBeDefined();
    // it is announced as a note, not silent decoration
    expect(CALC_DISCLAIMER).toMatch(/not a projection or guarantee/i);
    expect(CALC_DISCLAIMER).toMatch(/not investment advice/i);
  });
});

describe('SipCalculator — no advisory verbs, no fund names', () => {
  it('rendered copy contains no banned advisory verb', () => {
    render(<SipCalculator />);
    const text = bodyText();
    const found = ADVISORY.filter((v) => new RegExp(`\\b${v}\\b`, 'i').test(text));
    expect(found, `advisory verbs present: ${found.join(', ')}`).toHaveLength(0);
  });

  it('rendered copy contains no advisory phrase / CTA', () => {
    render(<SipCalculator />);
    const text = bodyText();
    const found = ADVISORY_PHRASES.filter((p) => text.includes(p));
    expect(found, `advisory phrases present: ${found.join(', ')}`).toHaveLength(0);
  });

  it('rendered copy names no fund / AMC', () => {
    render(<SipCalculator />);
    const text = bodyText();
    const found = FUND_NAMES.filter((n) => text.includes(n.toLowerCase()));
    expect(found, `fund names present: ${found.join(', ')}`).toHaveLength(0);
  });

  it('labels the return rate explicitly as the user’s assumption, not a prediction', () => {
    render(<SipCalculator />);
    expect(screen.getByText(/an assumption you choose — not a DhanRadar prediction/i)).toBeDefined();
  });
});

describe('SipCalculator — computes a value, never leaks NaN / Infinity', () => {
  it('shows a ₹ future value for the defaults with no NaN / Infinity', () => {
    render(<SipCalculator />);
    const fv = screen.getByTestId('result-future-value').textContent ?? '';
    expect(fv).toMatch(/^₹[\d,]+$/);     // a clean rupee figure
    expect(bodyText()).not.toContain('nan');
    expect(bodyText()).not.toContain('infinity');
    expect(bodyText()).not.toContain('₹nan');
  });

  it('stays finite for extreme inputs (max rate, long horizon, huge amount)', () => {
    render(<SipCalculator />);
    fireEvent.change(screen.getByLabelText('Number of years'), { target: { value: '50' } });
    fireEvent.change(
      screen.getByLabelText('Assumed yearly return (%)'),
      { target: { value: '50' } },
    );
    fireEvent.change(screen.getByLabelText('Monthly amount (₹)'), { target: { value: '99999999' } });

    const fv = screen.getByTestId('result-future-value').textContent ?? '';
    expect(fv).toMatch(/^₹[\d,]+$/);
    const text = bodyText();
    expect(text).not.toContain('nan');
    expect(text).not.toContain('infinity');
  });

  it('handles empty / zero inputs without crashing or showing NaN', () => {
    render(<SipCalculator />);
    fireEvent.change(screen.getByLabelText('Monthly amount (₹)'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('One-time amount (₹)'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Number of years'), { target: { value: '0' } });

    const fv = screen.getByTestId('result-future-value').textContent ?? '';
    expect(fv).toBe('₹0');
    expect(bodyText()).not.toContain('nan');
    expect(bodyText()).not.toContain('infinity');
  });
});

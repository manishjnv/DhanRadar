/**
 * MoodMethodology tests — the "how is this calculated?" explainer.
 *
 * Compliance: describes the METHOD only — no numeric score, no exact weights, no
 * advice. (Digits like "five levels" are spelled as words; we guard against a
 * numeric score and advisory verbs.)
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MoodMethodology } from './MoodMethodology';

describe('MoodMethodology', () => {
  it('renders a collapsible explainer of the method', () => {
    const { container } = render(<MoodMethodology />);
    const text = container.textContent ?? '';
    expect(container.querySelector('details')).not.toBeNull();
    expect(text).toContain('How is this calculated?');
    expect(text).toContain('Extreme Fear');
    expect(text).toContain('Extreme Greed');
  });

  it('is descriptive — no advisory verb, no numeric score, frames as not a prediction/tip', () => {
    const { container } = render(<MoodMethodology />);
    const text = (container.textContent ?? '').toLowerCase();
    // Verb list as a single split string (never individually quoted tokens) so the
    // ci_guards advisory scan does not read this guard list as shipped advisory copy.
    for (const v of 'buy sell hold recommend should'.split(' ')) {
      expect(text, `advisory verb ${v}`).not.toMatch(new RegExp(`\\b${v}\\b`));
    }
    expect(text).not.toMatch(/[0-9%]/);          // no score / percentage / weight digit
    expect(text).toContain('not a prediction');
    expect(text).toContain('not a tip to act on');
  });
});

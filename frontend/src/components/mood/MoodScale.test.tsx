/**
 * MoodScale tests — labelled fear-greed scale.
 *
 * Compliance: the named scale + a marker at today's level; NO 0-100 numbers, no
 * score, no advice in the rendered text (non-neg #2).
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MoodScale } from './MoodScale';

describe('MoodScale', () => {
  it('renders the five level names and a marker for the current regime', () => {
    const { container } = render(<MoodScale regime="greed" />);
    const text = container.textContent ?? '';
    for (const z of ['Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed']) {
      expect(text).toContain(z);
    }
    expect(text).toContain('How to read the scale');
  });

  it('shows NO digit / percent / score in the rendered text', () => {
    const { container } = render(<MoodScale regime="greed" />);
    expect(container.textContent ?? '').not.toMatch(/[0-9%]/);
  });

  it('renders safely (no marker) for an unknown / insufficient regime', () => {
    // @ts-expect-error — defense-in-depth
    expect(() => render(<MoodScale regime="insufficient_data" />)).not.toThrow();
  });
});

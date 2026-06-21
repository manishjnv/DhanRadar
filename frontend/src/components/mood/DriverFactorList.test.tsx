/**
 * DriverFactorList tests — numberless driver bars.
 *
 * Compliance-critical (non-neg #2): the rendered drivers section must contain NO
 * digit or percent character — only the factor label, the +/− marker, and a bar
 * whose width is a discrete tier (never a number/percentage in the text).
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { DriverFactorList } from './DriverFactorList';
import type { MoodFactor } from '@/features/mood/types';

const FACTORS: MoodFactor[] = [
  { label: 'Nifty Trend', tier: 'strong' },
  { label: 'India VIX', tier: 'moderate' },
  { label: 'News Sentiment', tier: 'slight' },
];

describe('DriverFactorList', () => {
  it('renders one row per factor with a bar each', () => {
    const { container } = render(
      <DriverFactorList heading="Supporting" items={FACTORS} marker="+" />,
    );
    expect(container.querySelectorAll('li')).toHaveLength(3);
    // each row has a magnitude bar (the inner fill div)
    expect(container.querySelectorAll('[role="presentation"]')).toHaveLength(3);
    expect(container.textContent).toContain('Nifty Trend');
    expect(container.textContent).toContain('Supporting');
  });

  it('renders distinct discrete fill widths per tier (no inline numeric value)', () => {
    const { container } = render(
      <DriverFactorList heading="Supporting" items={FACTORS} marker="+" />,
    );
    const fills = Array.from(container.querySelectorAll('[role="presentation"] > div'));
    const classes = fills.map((f) => f.className);
    expect(classes.some((c) => c.includes('w-full'))).toBe(true);   // strong
    expect(classes.some((c) => c.includes('w-2/3'))).toBe(true);    // moderate
    expect(classes.some((c) => c.includes('w-1/3'))).toBe(true);    // slight
    // no inline style width % leaked
    fills.forEach((f) => expect(f.getAttribute('style')).toBeNull());
  });

  it('renders NO digit or percent character in the drivers TEXT (non-neg #2)', () => {
    const { container } = render(
      <DriverFactorList heading="Counterweights" items={FACTORS} marker="−" />,
    );
    expect(container.textContent ?? '').not.toMatch(/[0-9%]/);
  });

  it('falls back safely for an unknown / missing tier (no crash, neutral bar)', () => {
    const weird: MoodFactor[] = [
      // @ts-expect-error — defense-in-depth: an unknown tier must not crash
      { label: 'Mystery Factor', tier: 'enormous' },
    ];
    const { container } = render(
      <DriverFactorList heading="Supporting" items={weird} marker="+" />,
    );
    const fill = container.querySelector('[role="presentation"] > div');
    expect(fill).not.toBeNull();
    // unknown tier → the slight (lowest) fallback width
    expect(fill?.className).toContain('w-1/3');
    expect(container.textContent ?? '').not.toMatch(/[0-9%]/);
  });

  it('renders nothing when there are no factors', () => {
    const { container } = render(
      <DriverFactorList heading="Supporting" items={[]} marker="+" />,
    );
    expect(container.firstChild).toBeNull();
  });
});

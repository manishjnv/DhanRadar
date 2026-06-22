/**
 * MoodFactorGuide tests — educational signal cards.
 *
 * Compliance: pure education — every signal named + explained, NO advisory verb,
 * no "tip to act" framing, no score/count. (Factual digits like "10Y" / "S&P 500"
 * are names, not a mood score, so we guard advisory verbs + counts, not all digits.)
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MoodFactorGuide, type SignalRole } from './MoodFactorGuide';

const ADVISORY =
  'buy sell hold switch avoid recommend should allocate overweight underweight'.split(' ');

describe('MoodFactorGuide', () => {
  it('renders a card per signal with name + description', () => {
    const { container } = render(<MoodFactorGuide />);
    const text = container.textContent ?? '';
    expect(text).toContain('What moves the mood');
    for (const name of ['Nifty Trend', 'India VIX', 'FII Flows', 'Put-Call Ratio', 'News Sentiment']) {
      expect(text).toContain(name);
    }
    // one card (li) per signal
    expect(container.querySelectorAll('li').length).toBe(11);
    // each card carries an icon (decorative svg)
    expect(container.querySelectorAll('svg').length).toBeGreaterThanOrEqual(11);
  });

  it('contains no advisory verb and frames itself as educational, not a tip', () => {
    const { container } = render(<MoodFactorGuide />);
    const text = (container.textContent ?? '').toLowerCase();
    const found = ADVISORY.filter((v) => new RegExp(`\\b${v}\\b`, 'i').test(text));
    expect(found, `advisory verbs: ${found.join(', ')}`).toHaveLength(0);
    expect(text).toContain('not a tip to act on');
  });

  it('shows Supporting/Counterweight + strength from signalState — and NO count', () => {
    const state = new Map<string, SignalRole>([
      ['Nifty Trend', { side: 'supporting', tier: 'strong' }],
      ['Brent Crude', { side: 'counterweight', tier: 'slight' }],
    ]);
    const { container } = render(<MoodFactorGuide signalState={state} />);
    const text = container.textContent ?? '';
    expect(text).toContain('Supporting');
    expect(text).toContain('Counterweight');
    expect(text).toContain('Strong');
    expect(text).toContain('Awaiting data'); // signals not in the map
    // honest coverage WITHOUT a count — no "N of 11" / "N/11"
    expect(text).not.toMatch(/\bof\s*11\b/i);
    expect(text).not.toMatch(/\d+\s*\/\s*11/);
  });

  it('omits the live state entirely when no signalState is given', () => {
    const { container } = render(<MoodFactorGuide />);
    const text = container.textContent ?? '';
    expect(text).not.toContain('Awaiting data');
    expect(text).not.toContain('Supporting');
  });
});

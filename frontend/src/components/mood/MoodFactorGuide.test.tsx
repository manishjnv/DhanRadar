/**
 * MoodFactorGuide tests — educational signal explainer.
 *
 * Compliance: pure education — every signal named + explained, NO advisory verb
 * and no "tip to act" framing. (Factual digits like "10-Year" / "S&P 500" are
 * names, not a mood score, so we guard advisory verbs, not digits.)
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MoodFactorGuide } from './MoodFactorGuide';

const ADVISORY =
  'buy sell hold switch avoid recommend should allocate overweight underweight'.split(' ');

describe('MoodFactorGuide', () => {
  it('names and explains the market signals', () => {
    const { container } = render(<MoodFactorGuide />);
    const text = container.textContent ?? '';
    expect(text).toContain('What moves the mood');
    for (const name of ['Nifty Trend', 'India VIX', 'FII Flows', 'Put-Call Ratio', 'News Sentiment']) {
      expect(text).toContain(name);
    }
    // each signal has a definition (dt + dd pairs)
    expect(container.querySelectorAll('dt').length).toBe(container.querySelectorAll('dd').length);
    expect(container.querySelectorAll('dt').length).toBeGreaterThanOrEqual(10);
  });

  it('contains no advisory verb and frames itself as educational, not a tip', () => {
    const { container } = render(<MoodFactorGuide />);
    const text = (container.textContent ?? '').toLowerCase();
    const found = ADVISORY.filter((v) => new RegExp(`\\b${v}\\b`, 'i').test(text));
    expect(found, `advisory verbs: ${found.join(', ')}`).toHaveLength(0);
    expect(text).toContain('not a tip to act on');
  });

  it('tags signals Live / Awaiting data from liveLabels — and shows NO count', () => {
    const { container } = render(
      <MoodFactorGuide liveLabels={new Set(['Nifty Trend', 'India VIX'])} />,
    );
    const text = container.textContent ?? '';
    expect(text).toContain('Live');
    expect(text).toContain('Awaiting data'); // the signals not in the set
    // honest coverage WITHOUT a count — no "N of 11" / "N/11" style number
    expect(text).not.toMatch(/\bof\s*11\b/i);
    expect(text).not.toMatch(/\d+\s*\/\s*11/);
  });

  it('omits the status tags entirely when no liveLabels are given', () => {
    const { container } = render(<MoodFactorGuide />);
    expect(container.textContent ?? '').not.toContain('Awaiting data');
  });
});

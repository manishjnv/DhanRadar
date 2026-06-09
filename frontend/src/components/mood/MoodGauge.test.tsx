/**
 * MoodGauge tests — must never crash the page on an out-of-enum regime.
 *
 * The backend emits a `data_unavailable` regime (with data_quality
 * "unavailable") when no snapshot has been computed. That value is outside the
 * known Regime set, so the gauge must degrade gracefully — it must NOT throw
 * (a thrown error here takes down the whole public /mood page via the Next.js
 * client error boundary).
 */
import { render } from '@testing-library/react';
import { MoodGauge, REGIME_DISPLAY } from './MoodGauge';

describe('MoodGauge', () => {
  it('renders a known regime without throwing', () => {
    expect(() =>
      render(<MoodGauge regime="neutral" confidenceBand="medium" />),
    ).not.toThrow();
  });

  it('does NOT crash on the backend "data_unavailable" sentinel regime', () => {
    expect(() => render(<MoodGauge regime="data_unavailable" confidenceBand="insufficient_data" />)).not.toThrow();
  });

  it('does NOT crash on an arbitrary unknown regime value', () => {
    // @ts-expect-error — defense-in-depth: any unknown value must be safe
    expect(() => render(<MoodGauge regime="totally_unknown" confidenceBand="low" />)).not.toThrow();
  });

  it('still exposes display words for all known regimes', () => {
    expect(REGIME_DISPLAY.neutral).toBe('Neutral');
    expect(REGIME_DISPLAY.insufficient_data).toBe('Insufficient Data');
  });
});

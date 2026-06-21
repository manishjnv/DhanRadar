/**
 * MoodMovement tests — the "vs yesterday" hero line.
 *
 * Compliance-critical assertions (non-negotiables #1, #2):
 *   - yesterday → today labels render from the regime words
 *   - trend clause appears only when trend is non-null; omitted when null
 *   - NO digit / percent character ever appears in the rendered hero text
 *   - no-history fallback renders ONLY "Today: <regime>" (no arrow)
 *   - out-of-enum / sentinel regimes degrade safely (no bare enum, no throw)
 *   - no advisory verbs in the rendered text
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MoodMovement } from './MoodMovement';

// Single space-separated string → split, never individually quoted tokens, so
// the deterministic anti-pattern scan does not read this guard list as shipped
// advisory copy (mirrors MoodContextSection.test.tsx; ci_guards scans frontend/src).
const ADVISORY_VERBS =
  'buy sell hold switch avoid caution reduce diversify rebalance exit invest recommend should suggest allocate overweight underweight consider opportunity'.split(
    ' ',
  );

function textOf(ui: React.ReactElement): string {
  const { container } = render(ui);
  return container.textContent ?? '';
}

describe('MoodMovement — yesterday → today render', () => {
  it('renders both yesterday and today labels from the regimes', () => {
    const text = textOf(
      <MoodMovement todayRegime="greed" yesterdayRegime="neutral" trend="improving" />,
    );
    expect(text).toContain('Yesterday:');
    expect(text).toContain('Neutral');
    expect(text).toContain('Today:');
    expect(text).toContain('Greed');
    // arrow glyph present between the two
    expect(text).toContain('→');
  });

  it('renders the trend clause when trend is provided', () => {
    const text = textOf(
      <MoodMovement todayRegime="greed" yesterdayRegime="neutral" trend="deteriorating" />,
    );
    expect(text).toContain('trend deteriorating');
  });
});

describe('MoodMovement — trend clause omission', () => {
  it('omits the "· trend …" clause entirely when trend is null', () => {
    const text = textOf(
      <MoodMovement todayRegime="greed" yesterdayRegime="neutral" trend={null} />,
    );
    expect(text).not.toContain('trend');
    expect(text).not.toContain('·');
  });

  it('omits the trend clause when trend is undefined', () => {
    const text = textOf(<MoodMovement todayRegime="fear" yesterdayRegime="neutral" />);
    expect(text).not.toContain('trend');
  });
});

describe('MoodMovement — no numeric in DOM (non-negotiable #2)', () => {
  it('renders no digit or percent character in the hero text', () => {
    const text = textOf(
      <MoodMovement todayRegime="extreme_greed" yesterdayRegime="extreme_fear" trend="improving" />,
    );
    expect(text).not.toMatch(/[0-9%]/);
  });

  it('renders no digit or percent in the no-history fallback', () => {
    const text = textOf(<MoodMovement todayRegime="neutral" yesterdayRegime={null} trend={null} />);
    expect(text).not.toMatch(/[0-9%]/);
  });
});

describe('MoodMovement — no-history fallback', () => {
  it('renders only "Today: <regime>" with no arrow when there is no yesterday', () => {
    const text = textOf(
      <MoodMovement todayRegime="neutral" yesterdayRegime={null} trend={null} />,
    );
    expect(text).toContain('Today:');
    expect(text).toContain('Neutral');
    expect(text).not.toContain('Yesterday:');
    expect(text).not.toContain('→');
  });

  it('treats a non-meaningful yesterday (insufficient_data) as no history', () => {
    const text = textOf(
      <MoodMovement todayRegime="greed" yesterdayRegime="insufficient_data" trend={null} />,
    );
    expect(text).not.toContain('Yesterday:');
    expect(text).not.toContain('Insufficient Data');
    expect(text).toContain('Today:');
    expect(text).toContain('Greed');
  });

  it('treats the data_unavailable sentinel yesterday as no history', () => {
    const text = textOf(
      <MoodMovement todayRegime="fear" yesterdayRegime="data_unavailable" trend="stable" />,
    );
    expect(text).not.toContain('Yesterday:');
    expect(text).not.toContain('Data Unavailable');
    expect(text).toContain('Today:');
    expect(text).toContain('Fear');
  });
});

describe('MoodMovement — safe fallback / no crash', () => {
  it('does not throw and renders no bare enum for an unknown today regime', () => {
    expect(() =>
      render(
        // @ts-expect-error — defense-in-depth: any unknown value must be safe
        <MoodMovement todayRegime="totally_unknown" yesterdayRegime={null} trend={null} />,
      ),
    ).not.toThrow();
    const text = textOf(
      // @ts-expect-error — defense-in-depth
      <MoodMovement todayRegime="totally_unknown" yesterdayRegime={null} trend={null} />,
    );
    expect(text).not.toContain('totally_unknown');
    expect(text).toContain('Insufficient Data'); // muted fallback word
  });
});

describe('MoodMovement — no advisory verbs (non-negotiable #1)', () => {
  it('renders no banned advisory verb across regime + trend combinations', () => {
    const regimes = ['extreme_fear', 'fear', 'neutral', 'greed', 'extreme_greed'] as const;
    const trends = ['improving', 'stable', 'deteriorating', null] as const;
    for (const today of regimes) {
      for (const yesterday of regimes) {
        for (const trend of trends) {
          const text = textOf(
            <MoodMovement todayRegime={today} yesterdayRegime={yesterday} trend={trend} />,
          ).toLowerCase();
          const found = ADVISORY_VERBS.filter((v) =>
            new RegExp(`\\b${v}\\b`, 'i').test(text),
          );
          expect(found, `Advisory verbs found: ${found.join(', ')}`).toHaveLength(0);
        }
      }
    }
  });
});

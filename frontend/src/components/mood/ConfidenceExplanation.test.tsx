/**
 * ConfidenceExplanation tests — the plain-language "why this confidence" note.
 *
 * Compliance-critical assertions (non-negotiables #1, #2):
 *   (a) each (data_quality, confidence_band) combination renders its expected
 *       plain-language explanation
 *   (b) an unknown / future enum value renders the neutral fallback, no throw
 *   (c) NO digit or percent character appears in the rendered confidence text
 *   plus: no advisory verbs across every combination
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import {
  ConfidenceExplanation,
  explainConfidence,
} from './ConfidenceExplanation';
import type { ConfidenceBand, DataQuality } from '@/features/mood/types';

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

const ALL_QUALITIES: DataQuality[] = ['ok', 'degraded', 'unavailable'];
const ALL_BANDS: ConfidenceBand[] = ['high', 'medium', 'low', 'insufficient_data'];

describe('ConfidenceExplanation — (data_quality, confidence_band) mapping', () => {
  it('ok / high → high-confidence read', () => {
    expect(explainConfidence('ok', 'high')).toBe(
      'Most market signals agreed today, so this is a high-confidence read.',
    );
  });

  it('ok / medium → medium-confidence read', () => {
    expect(explainConfidence('ok', 'medium')).toBe(
      'Market signals were mixed today, so this is a medium-confidence read.',
    );
  });

  it('ok / low → lower-confidence read', () => {
    expect(explainConfidence('ok', 'low')).toBe(
      'Only some market signals lined up today, so this is a lower-confidence read.',
    );
  });

  it('degraded / low → lower-confidence read (some signals available)', () => {
    expect(explainConfidence('degraded', 'low')).toBe(
      'Only some market signals were available today, so this is a lower-confidence read.',
    );
  });

  it('degraded / medium → still the "some signals" lower-confidence read', () => {
    expect(explainConfidence('degraded', 'medium')).toBe(
      'Only some market signals were available today, so this is a lower-confidence read.',
    );
  });

  it('any band with insufficient_data → too-few-signals read', () => {
    expect(explainConfidence('ok', 'insufficient_data')).toBe(
      'Too few market signals were available to publish a confident read today.',
    );
    expect(explainConfidence('degraded', 'insufficient_data')).toBe(
      'Too few market signals were available to publish a confident read today.',
    );
  });

  it('unavailable data_quality → too-few-signals read regardless of band', () => {
    for (const band of ALL_BANDS) {
      expect(explainConfidence('unavailable', band)).toBe(
        'Too few market signals were available to publish a confident read today.',
      );
    }
  });

  it('renders the mapped sentence into the DOM', () => {
    const text = textOf(
      <ConfidenceExplanation dataQuality="ok" confidenceBand="high" />,
    );
    expect(text).toContain('high-confidence read');
  });
});

describe('ConfidenceExplanation — unknown / future enum fallback', () => {
  const NEUTRAL =
    'Today’s confidence reflects how many market signals were available.';

  it('unknown data_quality falls back to the neutral sentence (no throw)', () => {
    // @ts-expect-error — defense-in-depth: unknown runtime value must be safe
    expect(explainConfidence('totally_unknown', 'high')).toBe(NEUTRAL);
  });

  it('unknown confidence_band with ok data_quality falls back to neutral', () => {
    // @ts-expect-error — defense-in-depth
    expect(explainConfidence('ok', 'totally_unknown')).toBe(NEUTRAL);
  });

  it('renders without throwing for unknown enum values, no bare enum key', () => {
    const text = textOf(
      // @ts-expect-error — defense-in-depth
      <ConfidenceExplanation dataQuality="weird_value" confidenceBand="weird_band" />,
    );
    expect(text).toBe(NEUTRAL);
    expect(text).not.toContain('weird_value');
    expect(text).not.toContain('weird_band');
  });
});

describe('ConfidenceExplanation — no numeric in DOM (non-negotiable #2)', () => {
  it('renders no digit or percent character for any valid combination', () => {
    for (const dq of ALL_QUALITIES) {
      for (const band of ALL_BANDS) {
        const text = textOf(
          <ConfidenceExplanation dataQuality={dq} confidenceBand={band} />,
        );
        expect(text, `digit/percent in "${dq}/${band}": ${text}`).not.toMatch(
          /[0-9%]/,
        );
      }
    }
  });
});

describe('ConfidenceExplanation — no advisory verbs (non-negotiable #1)', () => {
  it('renders no banned advisory verb for any valid combination', () => {
    for (const dq of ALL_QUALITIES) {
      for (const band of ALL_BANDS) {
        const text = textOf(
          <ConfidenceExplanation dataQuality={dq} confidenceBand={band} />,
        ).toLowerCase();
        const found = ADVISORY_VERBS.filter((v) =>
          new RegExp(`\\b${v}\\b`, 'i').test(text),
        );
        expect(found, `Advisory verbs in "${dq}/${band}": ${found.join(', ')}`).toHaveLength(0);
      }
    }
  });
});

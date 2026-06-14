/**
 * FactorStrengthBar — Feature 4 confidence factor visualisation.
 *
 * Renders one row per named confidence quality factor as a labelled progress bar.
 * Compliance invariants:
 *   - NO raw floats in DOM — values are string bands: "high" | "medium" | "low".
 *   - Labels are descriptive ("High signal"), never advisory ("buy signal").
 *   - Missing factor keys render nothing (graceful degradation for old reports).
 *   - Bar fill colour is the same warm palette used in WhyThisLabelPanel signals.
 *
 * Design tokens: CSS custom properties from tokens.css — no ad-hoc colours.
 */

import * as React from 'react';

type FactorStrength = 'high' | 'medium' | 'low';

const DISPLAY_NAMES: Record<string, string> = {
  consistency:   'Consistency',
  recency:       'Recency',
  volatility:    'Volatility',
  data_coverage: 'Data coverage',
};

// Ordered for stable rendering — backend dict order is not guaranteed.
const FACTOR_ORDER = ['consistency', 'recency', 'volatility', 'data_coverage'];

const FILL_PCT: Record<FactorStrength, number> = {
  high:   100,
  medium:  65,
  low:     33,
};

const FILL_COLOR: Record<FactorStrength, string> = {
  high:   'var(--dr-emerald)',
  medium: 'var(--dr-amber)',
  low:    'var(--text-muted)',
};

const STRENGTH_LABEL: Record<FactorStrength, string> = {
  high:   'High signal',
  medium: 'Medium signal',
  low:    'Low signal',
};

export interface FactorStrengthBarProps {
  factors: Record<string, FactorStrength>;
}

export function FactorStrengthBar({ factors }: FactorStrengthBarProps) {
  const rows = FACTOR_ORDER.filter((key) => key in factors);
  if (rows.length === 0) return null;

  return (
    <div
      data-testid="factor-strength-bar"
      style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
    >
      <p
        style={{
          margin: '0 0 4px',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          color: 'var(--text-muted)',
        }}
      >
        Signal quality
      </p>
      {rows.map((key) => {
        const strength = factors[key] as FactorStrength;
        const pct = FILL_PCT[strength];
        const color = FILL_COLOR[strength];
        const label = STRENGTH_LABEL[strength];
        const name = DISPLAY_NAMES[key] ?? key;

        return (
          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 90,
                flexShrink: 0,
                fontSize: 12,
                color: 'var(--text-secondary)',
                fontFamily: 'var(--dr-font-sans)',
              }}
            >
              {name}
            </span>
            {/* Track */}
            <div
              role="presentation"
              style={{
                flex: 1,
                height: 6,
                borderRadius: 3,
                background: 'var(--border)',
                overflow: 'hidden',
              }}
            >
              {/* Fill */}
              <div
                style={{
                  width: `${pct}%`,
                  height: '100%',
                  borderRadius: 3,
                  background: color,
                  transition: 'width 0.3s ease',
                }}
              />
            </div>
            <span
              style={{
                width: 90,
                flexShrink: 0,
                fontSize: 11,
                color: 'var(--text-muted)',
                fontFamily: 'var(--dr-font-sans)',
              }}
            >
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

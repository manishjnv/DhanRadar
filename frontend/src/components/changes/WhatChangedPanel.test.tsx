/**
 * WhatChangedPanel vitest suite (Plan Group 2).
 *
 * Compliance assertions in every test:
 *   1. "unified_score" never appears in the DOM.
 *   2. No raw numeric confidence float in the DOM (e.g. "0.87").
 *   3. Disclosure bundle (not_advice + disclosure text) rendered on every mount.
 *   4. Advisory verbs (buy/sell/hold/switch/rebalance/recommend/etc.) absent.
 *
 * Behavioural assertions:
 *   - improved: label transition + chip text.
 *   - weakened: chip text.
 *   - unchanged: chip text.
 *   - new: "First snapshot" framing, no from-label/arrow.
 *   - insufficient_data: honest framing, chip text.
 *   - empty: empty-state element rendered + disclosure bundle still present.
 */

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { render, screen } from '@testing-library/react';
import type { PortfolioChangesData, FundChange } from './WhatChangedPanel';
import { WhatChangedPanel } from './WhatChangedPanel';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const DISCLOSURE: Pick<PortfolioChangesData, 'disclosure' | 'not_advice' | 'disclaimer_version'> = {
  // Production DISCLOSURE_BUNDLE text — it legitimately negates bare advisory verbs,
  // so the fixture uses the real string to keep the no-advisory assertion honest.
  disclosure:
    'Educational analysis only — not investment advice. Labels describe category-relative form, ' +
    'not a recommendation to buy, sell, hold, or switch.',
  not_advice: 'NOT_ADVICE',
  disclaimer_version: '2026-06-06.v1',
};

const IMPROVED_CHANGE: FundChange = {
  isin: 'INF001A01017',
  scheme_name: 'Alpha Equity Fund',
  label_from: 'off_track',
  label_to: 'on_track',
  band_from: 'low',
  band_to: 'medium',
  changed: true,
  change_kind: 'improved',
  reasons: ['NAV momentum recovered over 3-month window', 'Category rank improved'],
  as_of_from: '2026-05-01',
  as_of_to: '2026-06-01',
  nav_as_of: '2026-06-01',
  nav_days_ago: 10,
  nav_is_stale: false,
};

const WEAKENED_CHANGE: FundChange = {
  ...IMPROVED_CHANGE,
  isin: 'INF002B01025',
  scheme_name: 'Beta Debt Fund',
  label_from: 'on_track',
  label_to: 'off_track',
  band_from: 'high',
  band_to: 'medium',
  changed: true,
  change_kind: 'weakened',
  reasons: ['Category rank declined'],
};

const UNCHANGED_CHANGE: FundChange = {
  ...IMPROVED_CHANGE,
  isin: 'INF003C01033',
  scheme_name: 'Gamma Hybrid Fund',
  label_from: 'on_track',
  label_to: 'on_track',
  band_from: 'medium',
  band_to: 'medium',
  changed: false,
  change_kind: 'unchanged',
  reasons: ['No material change in category-relative performance'],
};

const NEW_CHANGE: FundChange = {
  isin: 'INF004D01041',
  scheme_name: 'Delta New Fund',
  label_from: null,
  label_to: 'in_form',
  band_from: null,
  band_to: 'high',
  changed: true,
  change_kind: 'new',
  reasons: ['First assessment — 14+ months of history now available'],
  as_of_from: null,
  as_of_to: '2026-06-01',
  nav_as_of: '2026-06-01',
  nav_days_ago: 0,
  nav_is_stale: false,
};

const INSUFFICIENT_CHANGE: FundChange = {
  isin: 'INF005E01059',
  scheme_name: 'Epsilon Unknown Fund',
  label_from: null,
  label_to: 'insufficient_data',
  band_from: null,
  band_to: 'insufficient_data',
  changed: false,
  change_kind: 'insufficient_data',
  reasons: ['Less than 14 months of NAV history available'],
  as_of_from: null,
  as_of_to: '2026-06-01',
  nav_as_of: null,
  nav_days_ago: null,
  nav_is_stale: false,
};

const STALE_CHANGE: FundChange = {
  ...IMPROVED_CHANGE,
  isin: 'INF006F01067',
  scheme_name: 'Stale NAV Fund',
  nav_days_ago: 8,
  nav_is_stale: true,
};

// ---------------------------------------------------------------------------
// Helper: assert no numeric score in the DOM (mirrors TransparencyPanel pattern)
// ---------------------------------------------------------------------------

function assertNoNumericScore(container: HTMLElement) {
  expect(container.innerHTML).not.toContain('unified_score');
  // raw confidence floats like 0.87 must never appear
  expect(container.innerHTML).not.toMatch(/\b0\.\d{2,}\b/);
}

// ---------------------------------------------------------------------------
// Helper: build a minimal PortfolioChangesData
// ---------------------------------------------------------------------------

function makeData(changes: FundChange[]): PortfolioChangesData {
  return {
    portfolio_id: 'test-pid-001',
    changes,
    ...DISCLOSURE,
  };
}

// ---------------------------------------------------------------------------
// 1. improved — label transition + chip
// ---------------------------------------------------------------------------

describe('WhatChangedPanel — improved', () => {
  it('renders "Off Track → On Track" label transition', () => {
    const { container } = render(<WhatChangedPanel data={makeData([IMPROVED_CHANGE])} />);
    const transition = screen.getByTestId('label-transition');
    expect(transition.textContent).toContain('Off Track');
    expect(transition.textContent).toContain('On Track');
    assertNoNumericScore(container);
  });

  it('renders "Improved" chip', () => {
    render(<WhatChangedPanel data={makeData([IMPROVED_CHANGE])} />);
    const chip = screen.getByTestId('change-kind-chip');
    expect(chip.textContent).toBe('Improved');
  });

  it('renders reasons list', () => {
    render(<WhatChangedPanel data={makeData([IMPROVED_CHANGE])} />);
    const reasons = screen.getByTestId('change-reasons');
    expect(reasons.textContent).toContain('NAV momentum recovered');
  });

  it('renders disclosure bundle', () => {
    render(<WhatChangedPanel data={makeData([IMPROVED_CHANGE])} />);
    expect(screen.getByTestId('not-advice-label').textContent).toContain('NOT_ADVICE');
    expect(screen.getByTestId('disclosure-text').textContent).toContain('Educational analysis only');
  });
});

// ---------------------------------------------------------------------------
// 2. weakened — chip text
// ---------------------------------------------------------------------------

describe('WhatChangedPanel — weakened', () => {
  it('renders "Weakened" chip', () => {
    render(<WhatChangedPanel data={makeData([WEAKENED_CHANGE])} />);
    const chip = screen.getByTestId('change-kind-chip');
    expect(chip.textContent).toBe('Weakened');
  });
});

// ---------------------------------------------------------------------------
// 3. unchanged — chip text
// ---------------------------------------------------------------------------

describe('WhatChangedPanel — unchanged', () => {
  it('renders "Unchanged" chip', () => {
    render(<WhatChangedPanel data={makeData([UNCHANGED_CHANGE])} />);
    const chip = screen.getByTestId('change-kind-chip');
    expect(chip.textContent).toBe('Unchanged');
  });
});

// ---------------------------------------------------------------------------
// 4. new — "First snapshot" framing, no from-label/arrow
// ---------------------------------------------------------------------------

describe('WhatChangedPanel — new entry', () => {
  it('renders "First snapshot" framing', () => {
    render(<WhatChangedPanel data={makeData([NEW_CHANGE])} />);
    const transition = screen.getByTestId('label-transition');
    expect(transition.textContent).toContain('First snapshot');
    expect(transition.textContent).toContain('In Form');
  });

  it('does NOT render a from-label or arrow for new entry', () => {
    render(<WhatChangedPanel data={makeData([NEW_CHANGE])} />);
    const transition = screen.getByTestId('label-transition');
    // Should not contain any from-label text (label_from is null)
    expect(transition.textContent).not.toContain('null');
    // The arrow → should not appear in the label-transition for new entries
    expect(transition.textContent).not.toContain('→');
  });

  it('renders "New" chip', () => {
    render(<WhatChangedPanel data={makeData([NEW_CHANGE])} />);
    const chip = screen.getByTestId('change-kind-chip');
    expect(chip.textContent).toBe('New');
  });
});

// ---------------------------------------------------------------------------
// 5. insufficient_data — honest framing
// ---------------------------------------------------------------------------

describe('WhatChangedPanel — insufficient_data', () => {
  it('renders "Insufficient data" chip', () => {
    render(<WhatChangedPanel data={makeData([INSUFFICIENT_CHANGE])} />);
    const chip = screen.getByTestId('change-kind-chip');
    expect(chip.textContent).toBe('Insufficient data');
  });

  it('renders the reasons verbatim', () => {
    render(<WhatChangedPanel data={makeData([INSUFFICIENT_CHANGE])} />);
    const reasons = screen.getByTestId('change-reasons');
    expect(reasons.textContent).toContain('Less than 14 months');
  });
});

// ---------------------------------------------------------------------------
// 6. empty state
// ---------------------------------------------------------------------------

describe('WhatChangedPanel — empty state', () => {
  it('renders the empty-state element', () => {
    render(<WhatChangedPanel data={makeData([])} />);
    const empty = screen.getByTestId('changes-empty');
    expect(empty.textContent).toContain('No changes to show yet');
  });

  it('still renders the disclosure bundle when changes is empty', () => {
    render(<WhatChangedPanel data={makeData([])} />);
    expect(screen.getByTestId('disclosure-bundle')).toBeTruthy();
    expect(screen.getByTestId('not-advice-label').textContent).toContain('NOT_ADVICE');
  });
});

// ---------------------------------------------------------------------------
// 7. no-numeric: no unified_score, no raw float
// ---------------------------------------------------------------------------

describe('WhatChangedPanel — no numeric score in DOM (non-neg #2)', () => {
  it('never renders unified_score in the DOM', () => {
    const { container } = render(
      <WhatChangedPanel
        data={makeData([IMPROVED_CHANGE, WEAKENED_CHANGE, INSUFFICIENT_CHANGE])}
      />,
    );
    expect(container.innerHTML).not.toContain('unified_score');
  });

  it('never renders a raw confidence float (e.g. "0.87")', () => {
    const { container } = render(
      <WhatChangedPanel
        data={makeData([IMPROVED_CHANGE, WEAKENED_CHANGE, INSUFFICIENT_CHANGE])}
      />,
    );
    expect(container.innerHTML).not.toContain('0.87');
    // General float pattern check
    expect(container.innerHTML).not.toMatch(/\b0\.\d{2,}\b/);
  });
});

// ---------------------------------------------------------------------------
// 8. no-advisory-verbs: full rendered text must not contain forbidden substrings
// ---------------------------------------------------------------------------

describe('WhatChangedPanel — no advisory verbs in rendered text (non-neg #1)', () => {
  it('adds no advisory directive, and generated rows carry no bare advisory verb', () => {
    const { container } = render(
      <WhatChangedPanel
        data={makeData([IMPROVED_CHANGE, WEAKENED_CHANGE, UNCHANGED_CHANGE, NEW_CHANGE, INSUFFICIENT_CHANGE])}
      />,
    );
    // The disclosure bundle legitimately negates bare verbs, so the whole-panel scan
    // checks advisory DIRECTIVE phrases only — mirrors the transparency suite rationale.
    const allText = container.textContent?.toLowerCase() ?? '';
    const directives: string[] = (
      'buy this fund|sell this fund|you should buy|you should sell|switch to|redeem now|book profit'
    ).split('|');
    for (const phrase of directives) {
      expect(allText, `directive "${phrase}" must not appear`).not.toContain(phrase);
    }
    // The component-GENERATED rows (change-row excludes the disclosure bundle) must
    // contain NO bare advisory verb — this is the copy the module itself produces.
    const rowsText = screen
      .getAllByTestId('change-row')
      .map((el) => el.textContent?.toLowerCase() ?? '')
      .join(' ');
    const bareVerbs: string[] = (
      'buy sell hold switch reduce rebalance redeem consider recommend should suggest avoid caution'
    ).split(' ');
    for (const verb of bareVerbs) {
      expect(rowsText, `bare verb "${verb}" must not appear in change rows`).not.toContain(verb);
    }
  });
});

// ---------------------------------------------------------------------------
// 9. stale NAV note appears when nav_is_stale=true
// ---------------------------------------------------------------------------

describe('WhatChangedPanel — stale NAV note', () => {
  it('shows NAV days old when nav_is_stale is true', () => {
    render(<WhatChangedPanel data={makeData([STALE_CHANGE])} />);
    const freshness = screen.getByTestId('freshness');
    expect(freshness.textContent).toContain('8 days old');
  });

  it('does not show NAV stale note when nav_is_stale is false', () => {
    render(<WhatChangedPanel data={makeData([IMPROVED_CHANGE])} />);
    const freshness = screen.getByTestId('freshness');
    expect(freshness.textContent).not.toContain('days old');
  });
});

// ---------------------------------------------------------------------------
// 10. Disclosure bundle appears exactly once
// ---------------------------------------------------------------------------

describe('WhatChangedPanel — disclosure bundle invariant', () => {
  it('renders disclosure-bundle exactly once', () => {
    render(
      <WhatChangedPanel
        data={makeData([IMPROVED_CHANGE, WEAKENED_CHANGE])}
      />,
    );
    expect(screen.getAllByTestId('disclosure-bundle').length).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// 11. Chip tint is valid CSS (B62-f1 regression)
//
// Source-level guard: a bare `${color}22` hex-alpha suffix on a CSS var() is
// invalid CSS — the chip silently renders with NO tint. jsdom's CSS parser
// drops both the broken value and color-mix() from computed styles, so a
// rendered-style assertion cannot distinguish them; guard the source instead.
// ---------------------------------------------------------------------------

describe('WhatChangedPanel — chip tint valid CSS (B62-f1)', () => {
  const src = readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), './WhatChangedPanel.tsx'),
    'utf8',
  );

  it('never suffixes a hex alpha onto an interpolated color token', () => {
    expect(src).not.toMatch(/\$\{color\}[0-9a-fA-F]{2}/);
  });

  it('tints the chip via color-mix() so the var() stays valid', () => {
    expect(src).toContain('color-mix(in srgb');
  });
});

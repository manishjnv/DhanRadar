/**
 * WhatChangedPanel — "What Changed" surface for MF portfolio labels.
 * Plan Group 2.
 *
 * Compliance invariants:
 *   - NO numeric score / factor weights / raw confidence float in the DOM (non-neg #2).
 *     Allowed: confidence BAND label, ISO dates, nav_days_ago integer (data-quality metadata).
 *   - Advisory verb ban (non-neg #1): no buy/sell/hold/switch copy anywhere.
 *     Reasons are rendered VERBATIM from the backend — the component adds NO advisory copy.
 *   - insufficient_data rendered as deliberate honesty signal, not an error.
 *   - Disclosure bundle + NOT_ADVICE rendered on every mount (non-neg #9).
 *
 * Design tokens: Geist/warm from tokens.css (--surface, --border, --text-*, --dr-*).
 * No ad-hoc colours. No Tailwind arbitrary values beyond token references.
 */

import * as React from 'react';

// ---------------------------------------------------------------------------
// Types — mirrors the backend PortfolioChangesResponse schema exactly.
// unified_score has no corresponding field here (omitted by design).
// ---------------------------------------------------------------------------

export type ChangeKind =
  | 'improved'
  | 'weakened'
  | 'unchanged'
  | 'new'
  | 'insufficient_data';

export interface FundChange {
  isin: string;
  scheme_name: string | null;
  label_from: string | null;
  label_to: string;
  band_from: string | null;
  band_to: string;
  changed: boolean;
  change_kind: ChangeKind;
  reasons: string[];
  as_of_from: string | null;
  as_of_to: string;
  nav_as_of: string | null;
  nav_days_ago: number | null;
  nav_is_stale: boolean;
}

export interface PortfolioChangesData {
  portfolio_id: string;
  changes: FundChange[];
  disclosure: string;
  not_advice: string;
  disclaimer_version: string;
}

// ---------------------------------------------------------------------------
// Constants — display mappings (educational labels, non-advisory)
// ---------------------------------------------------------------------------

const LABEL_DISPLAY: Record<string, string> = {
  in_form:           'In Form',
  on_track:          'On Track',
  off_track:         'Off Track',
  out_of_form:       'Out of Form',
  insufficient_data: 'Insufficient Data',
};

/**
 * Change kind display — weakened uses amber (observation), not red (alarm).
 * Color is a CSS custom property from the live token file.
 */
const CHANGE_KIND_DISPLAY: Record<ChangeKind, { text: string; color: string }> = {
  improved:          { text: 'Improved',          color: 'var(--dr-emerald)' },
  weakened:          { text: 'Weakened',           color: 'var(--dr-amber)' },
  unchanged:         { text: 'Unchanged',          color: 'var(--text-muted)' },
  new:               { text: 'New',                color: 'var(--dr-royal)' },
  insufficient_data: { text: 'Insufficient data',  color: 'var(--text-muted)' },
};

/** Band display — text only, never a numeric. */
const BAND_DISPLAY: Record<string, string> = {
  high:              'High confidence',
  medium:            'Medium confidence',
  low:               'Low confidence',
  insufficient_data: 'Insufficient data',
};

function bandText(band: string | null): string | null {
  if (!band) return null;
  return BAND_DISPLAY[band] ?? band;
}

function labelText(label: string | null): string | null {
  if (!label) return null;
  return LABEL_DISPLAY[label] ?? label;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Change-kind chip — coloured with the mapped token, never numeric. */
function ChangeKindChip({ kind }: { kind: ChangeKind }) {
  const { text, color } = CHANGE_KIND_DISPLAY[kind] ?? {
    text: kind,
    color: 'var(--text-muted)',
  };
  return (
    <span
      data-testid="change-kind-chip"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 10px',
        borderRadius: 'var(--dr-r-full)',
        // token color at low alpha — color-mix keeps the CSS var valid (a bare
        // hex-alpha suffix on a var() is invalid CSS and renders no tint).
        background: `color-mix(in srgb, ${color} 13%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 33%, transparent)`,
        color,
        fontSize: 12,
        fontFamily: 'var(--dr-font-sans)',
        fontWeight: 600,
        letterSpacing: '0.02em',
      }}
    >
      {text}
    </span>
  );
}

/**
 * Label transition — "First snapshot: {label}" for new entries; "{from} → {to}" otherwise.
 * Guard: if label_from is null on a non-new entry, fall back to single-label display.
 */
function LabelTransition({ change }: { change: FundChange }) {
  const toLabel  = labelText(change.label_to)  ?? change.label_to;
  const toBand   = bandText(change.band_to)     ?? change.band_to;

  if (change.change_kind === 'new') {
    return (
      <p
        data-testid="label-transition"
        style={{
          margin: '6px 0 0',
          fontFamily: 'var(--dr-font-sans)',
          fontSize: 13,
          color: 'var(--text-secondary)',
        }}
      >
        First snapshot: <strong>{toLabel}</strong>
        {' '}
        <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
          · {toBand}
        </span>
      </p>
    );
  }

  const fromLabel = change.label_from ? (labelText(change.label_from) ?? change.label_from) : null;
  const fromBand  = change.band_from  ? (bandText(change.band_from)   ?? change.band_from)  : null;

  if (!fromLabel) {
    // Defensive: label_from was null on a non-new entry; render destination only.
    return (
      <p
        data-testid="label-transition"
        style={{
          margin: '6px 0 0',
          fontFamily: 'var(--dr-font-sans)',
          fontSize: 13,
          color: 'var(--text-secondary)',
        }}
      >
        <strong>{toLabel}</strong>
        {' '}
        <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
          · {toBand}
        </span>
      </p>
    );
  }

  return (
    <p
      data-testid="label-transition"
      style={{
        margin: '6px 0 0',
        fontFamily: 'var(--dr-font-sans)',
        fontSize: 13,
        color: 'var(--text-secondary)',
      }}
    >
      <span style={{ color: 'var(--text-muted)' }}>{fromLabel}</span>
      {' '}
      <span aria-hidden="true" style={{ color: 'var(--text-muted)' }}>→</span>
      {' '}
      <strong>{toLabel}</strong>
      {fromBand && (
        <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
          {' · '}{fromBand} → {toBand}
        </span>
      )}
      {!fromBand && (
        <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
          {' · '}{toBand}
        </span>
      )}
    </p>
  );
}

/** Reasons — rendered verbatim from the backend; no advisory copy added. */
function ReasonsBlock({ reasons }: { reasons: string[] }) {
  if (reasons.length === 0) return null;
  return (
    <ul
      data-testid="change-reasons"
      style={{
        margin: '8px 0 0',
        padding: 0,
        listStyle: 'none',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
    >
      {reasons.map((r, i) => (
        <li
          key={i}
          style={{
            fontFamily: 'var(--dr-font-sans)',
            fontSize: 12,
            color: 'var(--text-muted)',
            paddingLeft: 12,
            position: 'relative',
          }}
        >
          <span
            style={{ position: 'absolute', left: 0, color: 'var(--dr-royal)' }}
            aria-hidden="true"
          >
            ·
          </span>
          {r}
        </li>
      ))}
    </ul>
  );
}

/**
 * Freshness line — "Snapshot {from} → {to}" + optional NAV stale note.
 * Only ISO dates and the integer nav_days_ago appear — no numeric score.
 */
function FreshnessLine({ change }: { change: FundChange }) {
  const snapshotText = change.as_of_from
    ? `Snapshot ${change.as_of_from} → ${change.as_of_to}`
    : `Snapshot ${change.as_of_to}`;

  return (
    <div
      data-testid="freshness"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 8,
        marginTop: 8,
        fontSize: 12,
        fontFamily: 'var(--dr-font-sans)',
        color: 'var(--text-muted)',
      }}
    >
      <span>{snapshotText}</span>
      {change.nav_is_stale && change.nav_days_ago !== null && (
        <span
          style={{ color: 'var(--dr-amber)' }}
          aria-label={`NAV data is ${change.nav_days_ago} days old`}
        >
          · NAV {change.nav_days_ago} days old
        </span>
      )}
    </div>
  );
}

/** One fund change row */
function ChangeRow({ change }: { change: FundChange }) {
  const heading = change.scheme_name ?? change.isin;

  return (
    <div
      data-testid="change-row"
      style={{
        padding: '16px 0',
        borderBottom: '1px solid var(--border)',
      }}
    >
      {/* Header: scheme name + change kind chip */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 12,
        }}
      >
        <p
          style={{
            margin: 0,
            fontFamily: 'var(--dr-font-sans)',
            fontSize: 14,
            fontWeight: 600,
            color: 'var(--text)',
          }}
        >
          {heading}
        </p>
        <ChangeKindChip kind={change.change_kind} />
      </div>

      {/* Label transition */}
      <LabelTransition change={change} />

      {/* Reasons — verbatim from backend, no advisory copy */}
      <ReasonsBlock reasons={change.reasons} />

      {/* Freshness / date line */}
      <FreshnessLine change={change} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main exported component
// ---------------------------------------------------------------------------

export interface WhatChangedPanelProps {
  data: PortfolioChangesData;
  className?: string;
}

/**
 * WhatChangedPanel — renders the portfolio label-change payload.
 *
 * What it shows:
 *   - Per-fund: change-kind chip, label transition, verbatim backend reasons, freshness.
 *   - "new" entries: "First snapshot" framing — no from-label/arrow shown.
 *   - Empty state: calm no-changes message + disclosure bundle.
 *   - Disclosure bundle + NOT_ADVICE at the bottom (non-neg #9).
 *
 * What it never shows:
 *   - Numeric score / unified_score / factor weights / raw confidence float.
 *   - Advisory verbs (buy/sell/hold/switch/rebalance/recommend).
 *   - Any copy not supplied by the backend.
 */
export function WhatChangedPanel({ data, className }: WhatChangedPanelProps) {
  return (
    <section
      aria-label="What Changed"
      data-testid="what-changed-panel"
      style={{
        fontFamily: 'var(--dr-font-sans)',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--dr-r-xl)',
        padding: '20px 24px',
      }}
      className={className}
    >
      <h2
        style={{
          margin: '0 0 4px',
          fontSize: 16,
          fontWeight: 700,
          color: 'var(--text)',
          letterSpacing: '-0.01em',
        }}
      >
        What Changed
      </h2>
      <p
        style={{
          margin: '0 0 16px',
          fontSize: 12,
          color: 'var(--text-muted)',
        }}
      >
        How each fund&apos;s label and confidence shifted since the last snapshot.
      </p>

      {/* Change rows */}
      <div data-testid="changes-list">
        {data.changes.length === 0 ? (
          <p
            data-testid="changes-empty"
            style={{
              fontFamily: 'var(--dr-font-sans)',
              fontSize: 13,
              color: 'var(--text-muted)',
            }}
          >
            No changes to show yet.
          </p>
        ) : (
          data.changes.map((change) => (
            <ChangeRow key={change.isin} change={change} />
          ))
        )}
      </div>

      {/* Disclosure bundle — non-neg #9; renders on every mount */}
      <div
        data-testid="disclosure-bundle"
        role="note"
        aria-label="Educational disclaimer"
        style={{
          marginTop: 20,
          paddingTop: 16,
          borderTop: '1px solid var(--border)',
        }}
      >
        <p
          data-testid="not-advice-label"
          style={{
            margin: 0,
            fontSize: 11,
            fontWeight: 700,
            color: 'var(--text-muted)',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
        >
          {data.not_advice}
        </p>
        <p
          data-testid="disclosure-text"
          style={{
            margin: '4px 0 0',
            fontSize: 11,
            color: 'var(--text-muted)',
            lineHeight: 1.5,
          }}
        >
          {data.disclosure}
        </p>
      </div>
    </section>
  );
}

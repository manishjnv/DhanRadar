/**
 * TransparencyPanel — Data Transparency & Explainability surface
 * Plan Group 9 / PU2
 *
 * Compliance invariants:
 *   - NO numeric score / factor weights / raw confidence float in the DOM (non-neg #2).
 *     Allowed: confidence BAND label, data-quality driver strings, source names,
 *     freshness dates/ages (these are factual data-quality metadata, not the score).
 *   - Advisory verb ban (non-neg #1): no buy/sell/hold/switch copy anywhere.
 *   - insufficient_data rendered as deliberate honesty signal (PU2), not an error.
 *   - Disclosure bundle + NOT_ADVICE rendered on every mount (non-neg #9).
 *
 * Design tokens: Geist/warm from tokens.css (--surface, --border, --text-*, --dr-*).
 * No ad-hoc colours. No Tailwind arbitrary values beyond token references.
 */

import * as React from 'react';

// ---------------------------------------------------------------------------
// Types — mirrors the backend PortfolioTransparencyResponse schema exactly.
// unified_score has no corresponding field here (omitted by design).
// ---------------------------------------------------------------------------

export interface DataSource {
  name: string;
  type: string;
}

export interface FreshnessMeta {
  nav_as_of: string | null;
  nav_days_ago: number | null;
  is_stale: boolean;
  holdings_as_of: string | null;
}

export interface InsufficientDataRefusal {
  reason: string;
  detail: string;
}

export interface FundTransparency {
  isin: string;
  scheme_name: string;
  category: string | null;
  label: string;
  confidence_band: string;
  drivers: string[];
  what_would_change: string[];
  refusal: InsufficientDataRefusal | null;
  sources: DataSource[];
  freshness: FreshnessMeta;
  scored_at: string | null;
  model_version: string;
}

export interface PortfolioTransparencyData {
  portfolio_id: string;
  generated_at: string;
  funds: FundTransparency[];
  disclosure: string;
  not_advice: string;
  disclaimer_version: string;
}

// ---------------------------------------------------------------------------
// Constants — display mappings (educational labels, non-advisory)
// ---------------------------------------------------------------------------

const BAND_DISPLAY: Record<string, { label: string; color: string }> = {
  high:              { label: 'High confidence',         color: 'var(--dr-emerald)' },
  medium:            { label: 'Medium confidence',       color: 'var(--dr-amber)' },
  low:               { label: 'Low confidence',          color: 'var(--dr-red)' },
  insufficient_data: { label: 'Insufficient data',       color: 'var(--text-muted)' },
};

const LABEL_DISPLAY: Record<string, string> = {
  in_form:           'In Form',
  on_track:          'On Track',
  off_track:         'Off Track',
  out_of_form:       'Out of Form',
  insufficient_data: 'Insufficient Data',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Confidence band pill — shows band text only, never a numeric. */
function ConfidenceBadge({ band }: { band: string }) {
  const { label, color } = BAND_DISPLAY[band] ?? {
    label: band,
    color: 'var(--text-muted)',
  };
  return (
    <span
      data-testid="confidence-badge"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 10px',
        borderRadius: 'var(--dr-r-full)',
        background: `${color}22`,  // 13% opacity fill
        border: `1px solid ${color}55`,
        color,
        fontSize: 12,
        fontFamily: 'var(--dr-font-sans)',
        fontWeight: 600,
        letterSpacing: '0.02em',
      }}
    >
      {label}
    </span>
  );
}

/** Source chip — name + type tag */
function SourceChip({ source }: { source: DataSource }) {
  return (
    <span
      data-testid="source-chip"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 8px',
        borderRadius: 'var(--dr-r-md)',
        background: 'var(--surface-2)',
        border: '1px solid var(--border)',
        color: 'var(--text-secondary)',
        fontSize: 11,
        fontFamily: 'var(--dr-font-sans)',
      }}
    >
      <span style={{ fontWeight: 600 }}>{source.name}</span>
      <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
        · {source.type === 'nav_data' ? 'NAV data' : source.type === 'holdings' ? 'Holdings' : source.type}
      </span>
    </span>
  );
}

/** Freshness row — "updated N days ago" + stale warning */
function FreshnessRow({ freshness }: { freshness: FreshnessMeta }) {
  if (!freshness.nav_as_of) return null;
  return (
    <div
      data-testid="freshness-row"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 12,
        color: freshness.is_stale ? 'var(--dr-amber)' : 'var(--text-muted)',
        fontFamily: 'var(--dr-font-sans)',
      }}
    >
      <span
        aria-label={freshness.is_stale ? 'Data may be stale' : 'Data is recent'}
        style={{ fontSize: 14 }}
      >
        {freshness.is_stale ? '⚠️' : '✓'}
      </span>
      <span>
        {freshness.is_stale
          ? `NAV data is ${freshness.nav_days_ago} day(s) old \u2014 this label uses older price data`
          : `NAV updated ${freshness.nav_days_ago === 0 ? 'today' : `${freshness.nav_days_ago} day(s) ago`} (${freshness.nav_as_of})`}
      </span>
    </div>
  );
}

/** PU2 — Explicit insufficient_data refusal block. Educational, not an error. */
function RefusalBlock({ refusal }: { refusal: InsufficientDataRefusal }) {
  return (
    <div
      data-testid="refusal-block"
      role="note"
      aria-label="Insufficient data — assessment not available"
      style={{
        padding: '12px 16px',
        borderRadius: 'var(--dr-r-lg)',
        background: 'var(--surface-2)',
        border: '1px solid var(--border)',
        marginTop: 8,
      }}
    >
      <p
        style={{
          margin: 0,
          fontFamily: 'var(--dr-font-sans)',
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--text)',
        }}
      >
        {refusal.reason}
      </p>
      <p
        style={{
          margin: '4px 0 0',
          fontFamily: 'var(--dr-font-sans)',
          fontSize: 12,
          color: 'var(--text-muted)',
          lineHeight: 1.5,
        }}
      >
        {refusal.detail}
      </p>
    </div>
  );
}

/** One fund row in the transparency panel */
function FundRow({ fund }: { fund: FundTransparency }) {
  const labelDisplay = LABEL_DISPLAY[fund.label] ?? fund.label;

  return (
    <div
      data-testid="fund-row"
      style={{
        padding: '16px 0',
        borderBottom: '1px solid var(--border)',
      }}
    >
      {/* Header row: name + confidence badge */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <p
            style={{
              margin: 0,
              fontFamily: 'var(--dr-font-sans)',
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--text)',
            }}
          >
            {fund.scheme_name}
          </p>
          {fund.category && (
            <p
              style={{
                margin: '2px 0 0',
                fontFamily: 'var(--dr-font-sans)',
                fontSize: 12,
                color: 'var(--text-muted)',
              }}
            >
              {fund.category}
            </p>
          )}
        </div>
        <ConfidenceBadge band={fund.confidence_band} />
      </div>

      {/* Label (non-advisory) */}
      {fund.label !== 'insufficient_data' && (
        <p
          data-testid="fund-label"
          style={{
            margin: '8px 0 0',
            fontFamily: 'var(--dr-font-sans)',
            fontSize: 12,
            color: 'var(--text-secondary)',
          }}
        >
          Assessment: <strong>{labelDisplay}</strong>
        </p>
      )}

      {/* PU2 — refusal block */}
      {fund.refusal && <RefusalBlock refusal={fund.refusal} />}

      {/* Drivers (educational data-quality reasons) */}
      {fund.drivers.length > 0 && (
        <ul
          data-testid="drivers-list"
          style={{
            margin: '8px 0 0',
            padding: 0,
            listStyle: 'none',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          {fund.drivers.map((d, i) => (
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
                style={{
                  position: 'absolute',
                  left: 0,
                  color: 'var(--dr-royal)',
                }}
                aria-hidden="true"
              >
                ·
              </span>
              {d}
            </li>
          ))}
        </ul>
      )}

      {/* G10 — "What would change this" (educational, directional; never advice) */}
      {fund.what_would_change.length > 0 && (
        <div data-testid="what-would-change" style={{ marginTop: 12 }}>
          <p
            style={{
              margin: '0 0 4px',
              fontFamily: 'var(--dr-font-sans)',
              fontSize: 11,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              color: 'var(--text-muted)',
            }}
          >
            What would change this
          </p>
          <ul
            style={{
              margin: 0,
              padding: 0,
              listStyle: 'none',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
            }}
          >
            {fund.what_would_change.map((w, i) => (
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
                  style={{
                    position: 'absolute',
                    left: 0,
                    color: 'var(--dr-royal)',
                  }}
                  aria-hidden="true"
                >
                  ·
                </span>
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Sources */}
      {fund.sources.length > 0 && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 6,
            marginTop: 10,
          }}
        >
          {fund.sources.map((s, i) => (
            <SourceChip key={i} source={s} />
          ))}
        </div>
      )}

      {/* Freshness */}
      <div style={{ marginTop: 8 }}>
        <FreshnessRow freshness={fund.freshness} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main exported component
// ---------------------------------------------------------------------------

export interface TransparencyPanelProps {
  data: PortfolioTransparencyData;
  className?: string;
}

/**
 * TransparencyPanel — renders the full portfolio transparency payload.
 *
 * What it shows:
 *   - Per-fund: confidence band, educational drivers, source chips, freshness.
 *   - Per insufficient_data fund: explicit PU2 refusal block (not an error state).
 *   - Disclosure bundle + NOT_ADVICE at the bottom (non-neg #9).
 *
 * What it never shows:
 *   - Numeric score / unified_score / factor weights / raw confidence float.
 *   - Advisory verbs (buy/sell/hold/switch).
 */
export function TransparencyPanel({ data, className }: TransparencyPanelProps) {
  return (
    <section
      aria-label="Data Transparency"
      data-testid="transparency-panel"
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
        Data Transparency
      </h2>
      <p
        style={{
          margin: '0 0 16px',
          fontSize: 12,
          color: 'var(--text-muted)',
        }}
      >
        How confident is each assessment, what data it is based on, and how fresh
        that data is.
      </p>

      {/* Fund rows */}
      <div data-testid="funds-list">
        {data.funds.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            No fund data available yet.
          </p>
        ) : (
          data.funds.map((fund) => <FundRow key={fund.isin} fund={fund} />)
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

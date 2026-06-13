'use client';

/**
 * MoodContextSection — educational mood × portfolio tie-in surface (PU1).
 *
 * Renders the mood-context endpoint response as three deterministic observation
 * paragraphs + a regime chip + the disclosure bundle.
 *
 * Compliance:
 *   - No advisory verbs anywhere (non-neg #1) — observations rendered verbatim
 *     from backend; this component adds NO copy of its own
 *   - No numeric DhanRadar score / 0-100 value in DOM (non-neg #2)
 *   - regime chip uses REGIME_DISPLAY + REGIME_COLOR from MoodGauge with a safe
 *     fallback for unknown values (prior RCA: never a bare enum lookup)
 *   - disclosure + NOT_ADVICE rendered via <DisclosureBundle> in every data state
 *   - Empty / cold-start → valid section with honest empty observations, not an error
 *   - h2 present in EVERY state (loading / error / data) — section-shell invariant
 *
 * Design tokens: only existing design tokens — no ad-hoc colors or spacing.
 * Section shell mirrors WhatChangedSection / TransparencySection exactly.
 */

import * as React from 'react';
import { Skeleton } from '@/components/ui/Skeleton';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { REGIME_COLOR, REGIME_DISPLAY } from '@/components/mood/MoodGauge';
import { usePortfolioMoodContext } from '@/features/insights/api';
import type { MoodContextData } from '@/features/insights/types';

// ---------------------------------------------------------------------------
// Surface tokens — mirror WhatChangedSection / TransparencySection exactly
// ---------------------------------------------------------------------------
const surfaceStyle: React.CSSProperties = {
  fontFamily: 'var(--dr-font-sans)',
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--dr-r-xl)',
  padding: '20px 24px',
};

const headingStyle: React.CSSProperties = {
  margin: '0 0 16px',
  fontSize: 16,
  fontWeight: 700,
  color: 'var(--text)',
  letterSpacing: '-0.01em',
};

// ---------------------------------------------------------------------------
// RegimeChip — safe fallback for unknown regime values (prior RCA)
// ---------------------------------------------------------------------------
function RegimeChip({ regime }: { regime: string }) {
  // REGIME_COLOR / REGIME_DISPLAY index with the known Regime type; an unknown
  // future value will return undefined → fall back to the muted neutral token.
  const color =
    (REGIME_COLOR as Record<string, string>)[regime] ?? 'var(--text-muted)';
  const label =
    (REGIME_DISPLAY as Record<string, string>)[regime] ??
    regime.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <span
      data-testid="mood-regime-chip"
      style={{
        display: 'inline-block',
        padding: '2px 10px',
        borderRadius: 'var(--dr-r-full, 9999px)',
        fontSize: 12,
        fontWeight: 600,
        color,
        border: `1px solid ${color}`,
        background: 'transparent',
        letterSpacing: '0.03em',
      }}
    >
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Data state
// ---------------------------------------------------------------------------
function MoodContextContent({ data }: { data: MoodContextData }) {
  return (
    <>
      {/* Regime chip — only shown when regime is meaningful */}
      {data.regime !== 'data_unavailable' && data.regime_as_of && (
        <div className="mb-3">
          <RegimeChip regime={data.regime} />
          <span className="ml-2 text-xs text-text-secondary">
            as of {data.regime_as_of}
          </span>
        </div>
      )}
      {data.regime === 'data_unavailable' && (
        <div className="mb-3">
          <RegimeChip regime={data.regime} />
        </div>
      )}

      {/* Three deterministic observation paragraphs — rendered verbatim */}
      <div className="space-y-2">
        {data.observations.map((obs, i) => (
          <p
            key={i}
            className="text-sm text-text-secondary"
            data-testid={`mood-observation-${i}`}
          >
            {obs}
          </p>
        ))}
      </div>

      {/* Disclosure bundle — same rendering as other sections (non-neg #9) */}
      <div className="mt-4">
        <DisclosureBundle
          disclosure={data.disclosure}
          notAdvice={data.not_advice}
        />
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------
interface MoodContextSectionProps {
  portfolioId: string;
}

export function MoodContextSection({ portfolioId }: MoodContextSectionProps) {
  const { data, isError } = usePortfolioMoodContext(portfolioId);

  if (data) {
    return (
      <section
        aria-label="Market Mood Context"
        data-testid="mood-context-section"
        style={surfaceStyle}
      >
        <h2 style={headingStyle}>Market Mood Context</h2>
        <MoodContextContent data={data} />
      </section>
    );
  }

  return (
    <section
      aria-label="Market Mood Context"
      data-testid="mood-context-shell"
      style={surfaceStyle}
    >
      <h2 style={headingStyle}>Market Mood Context</h2>
      {isError ? (
        <p className="text-sm text-status-error" role="alert">
          Unable to load mood context. Please try again.
        </p>
      ) : (
        <div className="space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      )}
    </section>
  );
}

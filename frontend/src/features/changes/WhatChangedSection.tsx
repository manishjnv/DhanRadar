'use client';

/**
 * WhatChangedSection — fetch wrapper that mounts WhatChangedPanel on a page (B62-f2).
 *
 * Compliance:
 *   - All change copy is backend-authored and rendered verbatim by the panel
 *   - disclosure + NOT_ADVICE rendered inside WhatChangedPanel on every data state
 *     (non-neg #9) — this wrapper adds NO second bundle and NO copy of its own
 *   - No numeric DhanRadar score in DOM (non-neg #2) — enforced by the panel
 *   - Empty / cold-start → the panel's calm empty state, not an error
 *
 * The transient (loading / error / pre-fetch) shell reuses the PANEL's surface
 * tokens and h2 — not the Card shell — so the section keeps identical geometry
 * (var(--dr-r-xl) vs Card's rounded-lg=12px+shadow) and heading level across
 * fetch states (UI review cond-1/cond-2). It also renders for undefined data,
 * so the section never blanks out of the page mid-transition.
 */

import * as React from 'react';
import { Skeleton } from '@/components/ui/Skeleton';
import { WhatChangedPanel } from '@/components/changes';
import { usePortfolioChanges } from '@/features/changes/api';

interface WhatChangedSectionProps {
  portfolioId: string;
}

// Mirrors WhatChangedPanel's section surface + heading exactly (tokens only).
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

export function WhatChangedSection({ portfolioId }: WhatChangedSectionProps) {
  const { data, isError } = usePortfolioChanges(portfolioId);

  if (data) {
    return <WhatChangedPanel data={data} />;
  }

  return (
    <section aria-label="What Changed" data-testid="what-changed-shell" style={surfaceStyle}>
      <h2 style={headingStyle}>What Changed</h2>
      {isError ? (
        <p className="text-sm text-status-error" role="alert">
          Unable to load change history. Please try again.
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

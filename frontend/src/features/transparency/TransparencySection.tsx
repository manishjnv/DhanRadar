'use client';

/**
 * TransparencySection — fetch wrapper that mounts TransparencyPanel on a page (B60/PU2).
 *
 * Compliance:
 *   - All transparency copy is backend-authored and rendered verbatim by the panel
 *   - disclosure + NOT_ADVICE rendered inside TransparencyPanel on every data state
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
import { TransparencyPanel } from '@/components/transparency';
import { usePortfolioTransparency } from '@/features/transparency/api';

interface TransparencySectionProps {
  portfolioId: string;
}

// Mirrors TransparencyPanel's section surface tokens. Heading margin is 16px —
// NOT the panel's 4px (which is subtitle-tight); the shell has no subtitle, so
// 4px cramps the skeletons/error copy vs the sibling shells (UI review cond-1).
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

export function TransparencySection({ portfolioId }: TransparencySectionProps) {
  const { data, isError } = usePortfolioTransparency(portfolioId);

  if (data) {
    return <TransparencyPanel data={data} />;
  }

  return (
    <section aria-label="Data Transparency" data-testid="transparency-shell" style={surfaceStyle}>
      <h2 style={headingStyle}>Data Transparency</h2>
      {isError ? (
        <p className="text-sm text-status-error" role="alert">
          Unable to load transparency data. Please try again.
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

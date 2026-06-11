'use client';

/**
 * Portfolio Intelligence page — Fund Overlap + Concentration (Plan Group 3) +
 * What Changed label-movement explainer (Plan Group 2).
 *
 * Route: /portfolio/[portfolioId]/intelligence
 *
 * Compliance:
 *   - Educational analysis only — no advisory verbs anywhere on this page
 *   - disclosure + NOT_ADVICE rendered inside each section component
 *   - No numeric DhanRadar score in DOM (non-neg #2)
 *   - empty / cold-start → valid, non-error page
 *
 * Note: This is a client component because the sections use TanStack Query hooks.
 * `export const dynamic = 'force-dynamic'` is set here so Next.js never statically
 * renders a page whose content is user-specific and auth-gated (RCA lesson G8).
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import Link from 'next/link';
import { OverlapSection } from '@/features/portfolio/components/OverlapSection';
import { ConcentrationSection } from '@/features/portfolio/components/ConcentrationSection';
import { WhatChangedSection } from '@/features/changes/components/WhatChangedSection';

interface Props {
  params: { portfolioId: string };
}

export default function PortfolioIntelligencePage({ params }: Props) {
  const { portfolioId } = params;

  return (
    <main className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      {/* Back nav */}
      <nav className="mb-6" aria-label="Breadcrumb">
        <Link
          href="/(app)/dashboard"
          className="text-sm text-text-secondary hover:text-text-primary"
        >
          ← Dashboard
        </Link>
      </nav>

      <h1 className="mb-1 text-xl font-semibold text-text-primary">
        Portfolio Intelligence
      </h1>
      <p className="mb-6 text-sm text-text-secondary">
        Factual analysis of how your mutual fund holdings relate to each other.
        Educational only — not investment advice.
      </p>

      <div className="space-y-6">
        <OverlapSection portfolioId={portfolioId} />
        <ConcentrationSection portfolioId={portfolioId} />
        <WhatChangedSection portfolioId={portfolioId} />
      </div>
    </main>
  );
}

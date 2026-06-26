'use client';

/**
 * Calculator detail — /calculators/[slug]
 *
 * Deep-linkable detail page for a single calculator. Wrapped in <MaybeShell> like
 * the hub and Fund Detail V3 so anonymous visitors get clean standalone chrome
 * and logged-in users keep the workspace shell. The slug is resolved against the
 * calculator registry; unbuilt slugs render a clear "coming soon" state.
 */
import * as React from 'react';
import { useParams } from 'next/navigation';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { CalculatorDetail } from '@/components/calculators/CalculatorDetail';

function DetailInner() {
  const params = useParams<{ slug: string }>();
  return <CalculatorDetail slug={params.slug} />;
}

export default function CalculatorDetailPage() {
  return (
    <MaybeShell maxWidth="full">
      <React.Suspense fallback={null}>
        <DetailInner />
      </React.Suspense>
    </MaybeShell>
  );
}

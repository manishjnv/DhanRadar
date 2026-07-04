'use client';

/**
 * /onboarding — risk-profile setup page (cold-start gate).
 *
 * AuthGuard redirects unauthenticated users to /login before this renders.
 * AuthGuard also redirects users whose risk_profile is already set away from
 * this page (to /mf/portfolio), preventing re-entry once complete.
 *
 * Compliance: educational framing only, no advisory copy, no numerics in DOM.
 */

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { RiskQuiz } from '@/features/onboarding/RiskQuiz';

export default function OnboardingPage() {
  const router = useRouter();

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-10">
      {/* Page heading */}
      <div className="flex flex-col gap-1">
        <h1 className="text-h2 font-medium text-ink">Set your risk profile</h1>
        <p className="text-small text-ink-secondary">
          Answer five short questions so DhanRadar can tailor its educational
          market-intelligence views to your investment horizon and comfort with
          variability. This profile is for display purposes only and is{' '}
          <strong className="font-medium text-ink">not investment advice</strong>.
        </p>
      </div>

      {/* Quiz */}
      <RiskQuiz onComplete={() => router.replace('/mf/portfolio')} />
    </div>
  );
}

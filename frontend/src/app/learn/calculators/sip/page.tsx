/**
 * /learn/calculators/sip — generic SIP & compounding EDUCATIONAL calculator.
 *
 * Server Component (static, no backend fetch); NOT inside (app) route group →
 * no AuthGuard. Chrome (header + standing Disclaimer) provided by MaybeShell.
 * The interactive math lives in the client <SipCalculator/>.
 *
 * Standalone illustrative math only — not advice, not a DhanRadar projection,
 * and not tied to any fund / score / label / mood signal.
 */
import type { Metadata } from 'next';
import Link from 'next/link';
import { Calculator } from 'lucide-react';

import { MaybeShell } from '@/components/ui/MaybeShell';
import { SipCalculator } from '@/features/learn/calculators/SipCalculator';

// ---------------------------------------------------------------------------
// Static SEO metadata
// ---------------------------------------------------------------------------
export const metadata: Metadata = {
  title: 'SIP & Compounding Calculator — DhanRadar',
  description:
    'A free, generic compounding calculator: see how a monthly amount and a one-time amount could grow over time at a return rate you choose. Illustrative math only — not a projection or investment advice.',
  openGraph: {
    title: 'SIP & Compounding Calculator — DhanRadar',
    description:
      'See how a monthly amount and a one-time amount could grow over time at a return rate you choose. Illustrative math only — not investment advice.',
    type: 'website',
    siteName: 'DhanRadar',
  },
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function SipCalculatorPage() {
  return (
    <MaybeShell>
      {/* Page heading */}
      <div className="mb-6">
        <h1 className="text-h2 font-medium text-ink">SIP &amp; Compounding Calculator</h1>
        <p className="text-small text-ink-secondary mt-1">
          See how a regular monthly amount and a one-time amount could grow over time, using a
          yearly return rate you choose. This is illustrative compounding math — not a projection
          by DhanRadar.
        </p>
      </div>

      {/* Sibling /learn area link (internal cluster linking) */}
      <div className="mb-6">
        <Link
          href="/learn/concepts"
          className="inline-flex items-center gap-2 text-small text-royal hover:text-royal/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded"
        >
          <Calculator size={16} aria-hidden="true" />
          New to compounding and SIPs? Read the basics
        </Link>
      </div>

      <SipCalculator />
    </MaybeShell>
  );
}

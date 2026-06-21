/**
 * /pricing — Public marketing page
 *
 * Server Component (no 'use client').
 *
 * Compliance checklist (self-verified):
 *  #1  No advisory copy/labels. Labels: In Form / On Track / Off Track only.
 *      No buy/sell/switch/hold/exit/avoid/caution verbs in user-facing copy
 *      (appear ONLY in negation sentences: "we never tell you to buy, sell, or switch").
 *  #2  No numeric fund score, percentage-weight, or fair value in DOM.
 *      Plan prices (₹0 etc.) are prices, NOT fund scores — permitted.
 *  #9  <Disclaimer /> rendered at the bottom.
 *
 * Accessibility:
 *  - Semantic landmarks: <header> <main> <footer> <section aria-labelledby>
 *  - Focus-visible rings on all interactive elements (Button + LINK_RING class)
 *  - 44px minimum tap targets on nav/footer links (min-h-[44px])
 *  - Decorative icon images: alt=""
 *  - FAQ backed by <PricingFaq> client component with full aria wiring
 *
 * No backend fetch in this Server Component (avoids build-time ECONNREFUSED).
 * The <PricingPlans /> client component fetches /billing/plans on mount.
 */

import type { Metadata } from 'next';
import { SiteHeader } from '@/components/site/SiteHeader';
import { SiteFooter } from '@/components/site/SiteFooter';
import { PricingPlans } from '@/components/pricing/PricingPlans';
import { PricingFaq } from '@/components/pricing/PricingFaq';

// ---------------------------------------------------------------------------
// SEO metadata
// ---------------------------------------------------------------------------
export const metadata: Metadata = {
  title: 'Pricing — DhanRadar',
  description:
    'Start free — upload your CAS and get every fund labelled in about a minute. Founding Access is free until launch. Educational mutual-fund analytics, never investment advice.',
  openGraph: {
    title: 'Pricing — DhanRadar',
    description:
      'Start free — upload your CAS and get every fund labelled in about a minute. Founding Access is free until launch. Educational mutual-fund analytics, never investment advice.',
    type: 'website',
    locale: 'en_IN',
  },
};

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Feature comparison data
// A semantic table comparing the 3 tiers across key capabilities.
// Educational copy only — no advisory verbs, no numeric scores.
// ---------------------------------------------------------------------------
const COMPARISON_ROWS: {
  feature: string;
  free: string | boolean;
  plus: string | boolean;
  founding: string | boolean;
}[] = [
  {
    feature: 'CAS upload + fund labelling',
    free: true,
    plus: true,
    founding: true,
  },
  {
    feature: 'Category-relative labels (In Form / On Track / Off Track)',
    free: true,
    plus: true,
    founding: true,
  },
  {
    feature: 'Confidence bands (high / medium / low)',
    free: true,
    plus: true,
    founding: true,
  },
  {
    feature: 'Label explainers',
    free: true,
    plus: true,
    founding: true,
  },
  {
    feature: 'Market Mood',
    free: true,
    plus: true,
    founding: true,
  },
  {
    feature: 'Tax Education',
    free: true,
    plus: true,
    founding: true,
  },
  {
    feature: 'Portfolios',
    free: '1',
    plus: 'Unlimited',
    founding: 'Unlimited',
  },
  {
    feature: 'Label change history',
    free: false,
    plus: true,
    founding: true,
  },
  {
    feature: 'Automatic re-labelling on new NAVs',
    free: false,
    plus: true,
    founding: true,
  },
  {
    feature: 'Label-change alerts',
    free: false,
    plus: true,
    founding: true,
  },
  {
    feature: 'AI portfolio commentary (educational)',
    free: false,
    plus: true,
    founding: true,
  },
  {
    feature: 'Research assistant',
    free: false,
    plus: true,
    founding: true,
  },
  {
    feature: 'Founding-member status',
    free: false,
    plus: false,
    founding: true,
  },
  {
    feature: 'Help shape the product roadmap',
    free: false,
    plus: false,
    founding: true,
  },
];

// ---------------------------------------------------------------------------
// Cell helper — renders ✓ / × / string for table cells
// ---------------------------------------------------------------------------
function ComparisonCell({
  value,
  isHeader,
}: {
  value: string | boolean;
  isHeader?: boolean;
}) {
  if (typeof value === 'boolean') {
    return (
      <td
        className={`px-4 py-3 text-center text-body ${isHeader ? 'font-semibold' : ''}`}
      >
        {value ? (
          <span className="text-royal" aria-label="Included">
            ✓
          </span>
        ) : (
          <span className="text-ink-muted" aria-label="Not included">
            —
          </span>
        )}
      </td>
    );
  }
  return (
    <td
      className={`px-4 py-3 text-center text-small text-ink-secondary ${isHeader ? 'font-semibold text-ink' : ''}`}
    >
      {value}
    </td>
  );
}

// ---------------------------------------------------------------------------
// ComparisonTable
// ---------------------------------------------------------------------------
function ComparisonTable() {
  return (
    <section
      aria-labelledby="comparison-heading"
      className="mx-auto max-w-6xl px-6 py-12"
    >
      <h2
        id="comparison-heading"
        className="text-h2 font-semibold text-navy text-center mb-8"
      >
        Compare what&apos;s included
      </h2>

      {/* Horizontal scroll on small screens per subscription.md */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse">
          <thead>
            <tr className="border-b border-line">
              <th
                scope="col"
                className="px-4 py-3 text-left text-small font-semibold text-ink w-1/2"
              >
                Feature
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-center text-small font-semibold text-ink"
              >
                Free
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-center text-small font-semibold text-ink"
              >
                Plus
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-center text-small font-semibold text-ink bg-royal/10 rounded-t-md"
              >
                Founding Access
              </th>
            </tr>
          </thead>
          <tbody>
            {COMPARISON_ROWS.map((row, idx) => (
              <tr
                key={row.feature}
                className={`border-b border-line ${idx % 2 === 0 ? 'bg-bg' : 'bg-surface'}`}
              >
                <th
                  scope="row"
                  className="px-4 py-3 text-left text-small text-ink font-normal"
                >
                  {row.feature}
                </th>
                <ComparisonCell value={row.free} />
                <ComparisonCell value={row.plus} />
                {/* Founding column: subtle highlight */}
                <td
                  className="px-4 py-3 text-center text-small text-ink-secondary bg-royal/10"
                >
                  {typeof row.founding === 'boolean' ? (
                    row.founding ? (
                      <span className="text-royal font-semibold" aria-label="Included">
                        ✓
                      </span>
                    ) : (
                      <span className="text-ink-muted" aria-label="Not included">
                        —
                      </span>
                    )
                  ) : (
                    row.founding
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------
export default function PricingPage() {
  return (
    <div className="min-h-screen bg-bg">
      <SiteHeader />

      {/* ------------------------------------------------------------------ */}
      {/* Main                                                                */}
      {/* ------------------------------------------------------------------ */}
      <main>
        {/* Hero */}
        <section
          aria-labelledby="hero-heading"
          className="mx-auto max-w-6xl px-6 pt-16 pb-10 text-center"
        >
          {/* Eyebrow pill */}
          <span className="inline-flex items-center rounded-full border border-line bg-surface-2 px-3 py-1 text-caption text-ink-secondary mb-6">
            Educational market intelligence · Never advisory
          </span>

          <h1
            id="hero-heading"
            className="text-h1 font-semibold text-navy mb-4"
          >
            Simple pricing. Start free.
          </h1>

          <p className="text-body text-ink-secondary max-w-xl mx-auto">
            Upload your CAS and understand every fund you own — for free,
            forever. Founding Access is also free until we launch publicly.
            Educational analytics only; we never give investment advice.
          </p>
        </section>

        {/* Pricing plan cards */}
        <PricingPlans />

        {/* Feature comparison table */}
        <ComparisonTable />

        {/* FAQ section */}
        <section
          aria-labelledby="faq-heading"
          className="bg-surface-2 border-y border-line"
        >
          <div className="mx-auto max-w-2xl px-6 py-16">
            <h2
              id="faq-heading"
              className="text-h2 font-semibold text-navy text-center mb-10"
            >
              Frequently asked
            </h2>
            <PricingFaq />
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

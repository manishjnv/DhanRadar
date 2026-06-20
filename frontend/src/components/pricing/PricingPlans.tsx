'use client';

/**
 * PricingPlans — 3-card pricing grid with API hydration.
 *
 * Compliance checklist:
 *  #1  No advisory verbs (buy/sell/switch/hold/exit/avoid/caution) in feature copy.
 *  #2  No numeric fund score, percentage-weight, or fair value in DOM.
 *       (Plan prices in ₹ are prices, not fund scores — permitted.)
 *  #8  Tokens only — no inline hex colours, no text-[Npx].
 *
 * Data states (4):
 *  - loading    : static prices shown immediately; subtle pulse on Plus price only.
 *  - success[]  : each PlanOut matched by id/name; price overridden if matched.
 *  - success[]  empty: keep all static copy (expected pre-launch state).
 *  - error/503  : catch ApiError, keep static copy, show quiet indicator.
 *
 * Layout:
 *  - Mobile: stacked, Founding Access card first (source order + lg:order).
 *  - Desktop (lg): 3-column grid, Free | Plus | Founding in reading order.
 *  - Founding Access card: border-2 border-royal to highlight as popular.
 */

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Check, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardFooter } from '@/components/ui/Card';
import { api, ApiError } from '@/lib/apiClient';

// ---------------------------------------------------------------------------
// API shape
// ---------------------------------------------------------------------------
interface PlanOut {
  id: string;
  name: string;
  price_inr: number;
  interval: string;
  features: unknown[];
}

// ---------------------------------------------------------------------------
// Static plan definitions (SSR-visible fallback — must render immediately)
// ---------------------------------------------------------------------------

interface StaticPlan {
  id: string;
  name: string;
  eyebrow: string;
  priceLabel: string;
  priceNote: string | null;
  interval: string;
  features: string[];
  popular: boolean;
  cta: React.ReactNode;
  ctaCaption: string | null;
}

const STATIC_PLANS: StaticPlan[] = [
  {
    id: 'free',
    name: 'Free',
    eyebrow: 'FREE',
    priceLabel: '₹0',
    priceNote: null,
    interval: 'forever',
    popular: false,
    features: [
      'Upload your CAS and get every fund labelled',
      'Plain-English, category-relative labels (In Form / On Track / Off Track)',
      'Confidence bands (high / medium / low) — never a numeric score',
      'Basic explainers for each label',
      'Market Mood + Tax Education',
      '1 portfolio',
    ],
    cta: (
      <Button variant="outline" size="md" asChild className="w-full">
        <Link href="/signup">Get started — free</Link>
      </Button>
    ),
    ctaCaption: null,
  },
  {
    id: 'plus',
    name: 'DhanRadar Plus',
    eyebrow: 'PLUS',
    priceLabel: '₹—',
    priceNote: 'Pricing coming soon',
    interval: '',
    popular: false,
    features: [
      'Everything in Free',
      'Tracking history — see how each label changes over time',
      'Automatic re-scoring when new NAVs arrive',
      'Alerts when a fund\'s label changes',
      'Multiple portfolios',
      'AI portfolio commentary (educational)',
      'Research assistant',
    ],
    cta: (
      <Button variant="secondary" size="md" disabled className="w-full">
        Coming soon
      </Button>
    ),
    ctaCaption: 'Paid checkout opens at launch.',
  },
  {
    id: 'founding',
    name: 'Founding Access',
    eyebrow: 'FOUNDING',
    priceLabel: 'Free',
    priceNote: 'until public launch',
    interval: '',
    popular: true,
    features: [
      'Everything in Plus',
      'Free until public launch — plus a grace window after',
      'Founding-member status, locked in early',
      'Help shape what we build next',
    ],
    cta: (
      <Button variant="primary" size="md" asChild className="w-full">
        <Link href="/signup">Get Founding Access</Link>
      </Button>
    ),
    ctaCaption: null,
  },
];

// ---------------------------------------------------------------------------
// Feature row
// ---------------------------------------------------------------------------
function FeatureRow({ text }: { text: string }) {
  return (
    <li className="flex items-start gap-2">
      <Check
        aria-hidden="true"
        size={16}
        strokeWidth={2}
        className="mt-0.5 shrink-0 text-royal"
      />
      <span className="text-small text-ink-secondary">{text}</span>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Individual plan card
// ---------------------------------------------------------------------------
function PlanCard({
  plan,
  overridePrice,
  isLoading,
}: {
  plan: StaticPlan;
  overridePrice: { label: string; interval: string } | null;
  isLoading: boolean;
}) {
  const displayPrice = overridePrice ? overridePrice.label : plan.priceLabel;
  const displayInterval = overridePrice ? overridePrice.interval : plan.interval;

  return (
    <Card
      className={`
        flex flex-col
        ${plan.popular ? 'border-2 border-royal' : ''}
      `}
    >
      <CardBody className="flex flex-col gap-4 px-6 py-6">
        {/* Popular badge */}
        {plan.popular && (
          <div className="flex items-center gap-1.5">
            <Sparkles
              aria-hidden="true"
              size={14}
              strokeWidth={1.75}
              className="text-royal"
            />
            <span className="text-caption font-semibold text-royal">
              Founding member
            </span>
          </div>
        )}

        {/* Plan eyebrow */}
        <p className="text-caption font-mono uppercase tracking-wide text-royal">
          {plan.eyebrow}
        </p>

        {/* Plan name */}
        <h3 className="text-h3 font-semibold text-navy">{plan.name}</h3>

        {/* Price */}
        <div className="flex flex-col gap-0.5">
          <div
            className={`
              text-h1 font-mono tabular-nums text-navy
              ${isLoading && plan.id === 'plus' ? 'animate-pulse text-ink-muted' : ''}
            `}
          >
            {displayPrice}
          </div>
          {displayInterval && (
            <span className="text-small text-ink-muted">/ {displayInterval}</span>
          )}
          {!overridePrice && plan.priceNote && (
            <span className="text-caption text-ink-muted">{plan.priceNote}</span>
          )}
        </div>

        {/* Feature list */}
        <ul className="flex flex-col gap-2 mt-2">
          {plan.features.map((f) => (
            <FeatureRow key={f} text={f} />
          ))}
        </ul>
      </CardBody>

      <CardFooter className="flex flex-col items-stretch gap-2 px-6 py-4 border-t border-line">
        {plan.cta}
        {plan.ctaCaption && (
          <p className="text-caption text-ink-muted text-center">
            {plan.ctaCaption}
          </p>
        )}
      </CardFooter>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// PricingPlans — main client component
// ---------------------------------------------------------------------------
export function PricingPlans() {
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>(
    'idle',
  );
  const [apiPlans, setApiPlans] = useState<PlanOut[]>([]);
  const [showIndicative, setShowIndicative] = useState(false);

  useEffect(() => {
    setStatus('loading');
    api
      .get<PlanOut[]>('/billing/plans')
      .then((data) => {
        setApiPlans(Array.isArray(data) ? data : []);
        setStatus('done');
      })
      .catch((err) => {
        // ApiError (incl. 503) or network failure — keep static, show quiet note
        if (err instanceof ApiError || err instanceof Error) {
          setShowIndicative(true);
        }
        setStatus('error');
      });
  }, []);

  const isLoading = status === 'loading' || status === 'idle';

  /** For a static plan, find a matching PlanOut by id (case-insensitive) or name. */
  function getOverride(
    plan: StaticPlan,
  ): { label: string; interval: string } | null {
    if (apiPlans.length === 0) return null;
    const match = apiPlans.find(
      (p) =>
        p.id.toLowerCase() === plan.id.toLowerCase() ||
        p.name.toLowerCase() === plan.name.toLowerCase(),
    );
    if (!match) return null;
    return {
      label: `₹${match.price_inr.toLocaleString('en-IN')}`,
      interval: match.interval,
    };
  }

  // On mobile: Founding first (popular), Free second, Plus third.
  // On desktop (lg:): Free | Plus | Founding (reading order via order classes).
  return (
    <section aria-labelledby="plans-heading" className="py-12">
      <h2 id="plans-heading" className="sr-only">
        Pricing plans
      </h2>

      {showIndicative && (
        <p className="text-caption text-ink-muted text-center mb-4">
          Showing indicative pricing.
        </p>
      )}

      {/*
        Source order: Founding (popular) | Free | Plus
        On lg screens: reorder via order-* so it reads Free | Plus | Founding
      */}
      <div className="grid gap-6 max-w-6xl mx-auto px-6 lg:grid-cols-3">
        {/* Founding Access — first in source (mobile lead), last on desktop */}
        <div className="lg:order-3">
          <PlanCard
            plan={STATIC_PLANS[2]}
            overridePrice={getOverride(STATIC_PLANS[2])}
            isLoading={isLoading}
          />
        </div>

        {/* Free — second in source, first on desktop */}
        <div className="lg:order-1">
          <PlanCard
            plan={STATIC_PLANS[0]}
            overridePrice={getOverride(STATIC_PLANS[0])}
            isLoading={isLoading}
          />
        </div>

        {/* DhanRadar Plus — third in source, second on desktop */}
        <div className="lg:order-2">
          <PlanCard
            plan={STATIC_PLANS[1]}
            overridePrice={getOverride(STATIC_PLANS[1])}
            isLoading={isLoading}
          />
        </div>
      </div>
    </section>
  );
}

export default PricingPlans;

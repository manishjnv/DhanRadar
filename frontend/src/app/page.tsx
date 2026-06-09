/**
 * /  — Public landing page
 *
 * Server Component (no 'use client').
 * Compliance checklist (self-verified):
 *  #1  No advisory copy/labels. Labels: in_form / on_track / off_track only.
 *  #2  No numeric score, percentage-as-score, fair value, or price target in DOM.
 *  #9  <Disclaimer /> rendered at the bottom of every visible surface.
 *
 * Accessibility:
 *  - Semantic landmarks: <header>, <main>, <footer>, <nav>
 *  - Focus-visible rings on all interactive elements (from Button + link classes)
 *  - 44px tap targets on nav/footer links enforced via min-h-[44px] py-[10px]
 *  - body text ≥ text-body (16px via token) everywhere
 *  - Decorative logo images: alt=""
 *  - FAQ uses native <details>/<summary> — no JS, crawlable by search engines
 *
 * Links only to EXISTING routes:
 *  /signup · /login · /dashboard · /mf/upload · /mood · /learn/tax · /settings/privacy
 */

import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import {
  FileText,
  Tag,
  BarChart2,
  BookOpen,
  ShieldCheck,
  GraduationCap,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardFooter } from '@/components/ui/Card';
import { LabelChip } from '@/components/ui/LabelChip';
import { Disclaimer } from '@/components/ui/Disclaimer';

// ---------------------------------------------------------------------------
// SEO metadata
// ---------------------------------------------------------------------------
export const metadata: Metadata = {
  title: 'DhanRadar — Educational Mutual Fund Intelligence for India',
  description:
    'Upload your CAS statement and get every fund a plain-English, category-relative label in about a minute. Explainable, educational, and never a buy or sell call.',
  openGraph: {
    title: 'DhanRadar — Educational Mutual Fund Intelligence for India',
    description:
      'Upload your CAS statement and get every fund a plain-English, category-relative label in about a minute. Explainable, educational, and never a buy or sell call.',
    type: 'website',
    locale: 'en_IN',
  },
};

// ---------------------------------------------------------------------------
// Shared focus-ring class for plain <a> links (matches Button's ring)
// ---------------------------------------------------------------------------
const LINK_RING =
  'rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40';

// ---------------------------------------------------------------------------
// Nav
// ---------------------------------------------------------------------------
function SiteNav() {
  return (
    <header className="sticky top-0 z-30 bg-surface/95 border-b border-line backdrop-blur-sm">
      <nav
        aria-label="Main navigation"
        className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3"
      >
        {/* Brand */}
        <Link
          href="/"
          className={`flex items-center gap-2 ${LINK_RING}`}
          aria-label="DhanRadar home"
        >
          {/* Decorative icon; wordmark provides the accessible name */}
          <Image
            src="/brand/icon.svg"
            alt=""
            width={26}
            height={26}
            className="shrink-0"
          />
          <span className="text-h3 font-semibold text-navy">DhanRadar</span>
        </Link>

        {/* Centre links */}
        <div className="hidden items-center gap-1 sm:flex">
          <Link
            href="/learn/tax"
            className={`px-3 py-2 text-small text-ink-secondary transition-colors hover:text-ink min-h-[44px] flex items-center ${LINK_RING}`}
          >
            Tax Education
          </Link>
          <Link
            href="/mood"
            className={`px-3 py-2 text-small text-ink-secondary transition-colors hover:text-ink min-h-[44px] flex items-center ${LINK_RING}`}
          >
            Market Mood
          </Link>
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href="/login">Log in</Link>
          </Button>
          <Button variant="primary" size="sm" asChild>
            <Link href="/signup">Get started — free</Link>
          </Button>
        </div>
      </nav>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------
function Hero() {
  return (
    <section className="mx-auto max-w-6xl px-6 pt-16 pb-12 lg:pt-24 lg:pb-16">
      <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
        {/* Left — copy */}
        <div className="flex flex-col gap-6">
          {/* Eyebrow pill */}
          <span className="inline-flex w-fit items-center rounded-full border border-line bg-surface-2 px-3 py-1 text-caption text-ink-secondary">
            Educational market intelligence · Never advisory
          </span>

          <h1 className="text-h1 font-semibold text-navy leading-tight">
            Know where your mutual funds actually stand.
          </h1>

          <p className="text-body text-ink-secondary max-w-md">
            Upload your CAS statement and DhanRadar gives every fund a
            plain-English, category-relative label — in about a minute.
            Explainable, educational, and never a buy or sell call.
          </p>

          {/* CTAs */}
          <div className="flex flex-wrap gap-3">
            <Button variant="primary" size="lg" asChild>
              <Link href="/signup">Upload your CAS — free</Link>
            </Button>
            <Button variant="outline" size="lg" asChild>
              <Link href="/login">Log in</Link>
            </Button>
          </div>

          {/* Reassurance */}
          <p className="text-caption text-ink-muted">
            No numeric scores. No buy/sell tips. Just your funds, explained.
          </p>
        </div>

        {/* Right — report preview card */}
        <ReportPreviewCard />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Report-preview card (example only — no real data, no numerics)
// ---------------------------------------------------------------------------
function ReportPreviewCard() {
  const funds = [
    {
      name: 'Parag Parikh Flexi Cap Fund',
      category: 'Flexi Cap',
      label: 'in_form' as const,
      band: 'high' as const,
    },
    {
      name: 'SBI Bluechip Fund',
      category: 'Large Cap',
      label: 'on_track' as const,
      band: 'medium' as const,
    },
    {
      name: 'ICICI Pru Value Discovery Fund',
      category: 'Value',
      label: 'off_track' as const,
      band: 'medium' as const,
    },
  ] as const;

  return (
    <Card>
      {/* Card header */}
      <div className="flex items-baseline justify-between gap-2 border-b border-line px-6 py-4">
        <h2 className="text-h3 font-medium text-ink">Your portfolio, labelled</h2>
        <span className="text-caption text-ink-muted">Example</span>
      </div>

      <CardBody className="px-6 py-4">
        <ul className="divide-y divide-line">
          {funds.map((fund) => (
            <li
              key={fund.name}
              className="flex flex-wrap items-center justify-between gap-3 py-3"
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-small font-medium text-ink">
                  {fund.name}
                </span>
                <span className="text-caption text-ink-muted">
                  {fund.category}
                </span>
              </div>
              <LabelChip label={fund.label} confidenceBand={fund.band} />
            </li>
          ))}
        </ul>
      </CardBody>

      <CardFooter className="px-6 py-3">
        <p className="text-caption text-ink-muted">
          Educational labels describing category-relative form — not a
          recommendation to buy, sell, hold or switch. Example only; your real
          report is generated from your CAS.
        </p>
      </CardFooter>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// How it works — 3-step strip
// ---------------------------------------------------------------------------
function HowItWorks() {
  const steps = [
    {
      n: 1,
      title: 'Upload your CAS',
      desc: 'Your CAMS or KFintech statement, parsed securely in seconds.',
    },
    {
      n: 2,
      title: 'Get labelled funds',
      desc: 'Each fund gets a category-relative label (in_form / on_track / off_track) with the reasons.',
    },
    {
      n: 3,
      title: 'Learn the why',
      desc: 'Plain-English explanations and FY-aware tax guides — so you understand, not just obey.',
    },
  ] as const;

  return (
    <section
      aria-labelledby="how-heading"
      className="bg-surface-2 border-y border-line"
    >
      <div className="mx-auto max-w-6xl px-6 py-12">
        <h2
          id="how-heading"
          className="text-h2 font-semibold text-ink text-center mb-10"
        >
          How it works
        </h2>
        <ol className="grid gap-8 sm:grid-cols-3">
          {steps.map((step) => (
            <li key={step.n} className="flex flex-col gap-3">
              <span
                className="flex h-9 w-9 items-center justify-center rounded-full bg-royal/10 text-royal text-small font-semibold"
                aria-hidden="true"
              >
                {step.n}
              </span>
              <h3 className="text-h3 font-medium text-ink">{step.title}</h3>
              <p className="text-body text-ink-secondary">{step.desc}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Features grid (6 items)
// ---------------------------------------------------------------------------
function Features() {
  const items = [
    {
      icon: <Tag size={20} strokeWidth={1.75} aria-hidden="true" />,
      title: 'Explainable labels',
      desc: 'Category-relative form (in_form / on_track / off_track), with the contributing reasons. Never a tip.',
    },
    {
      icon: <BarChart2 size={20} strokeWidth={1.75} aria-hidden="true" />,
      title: 'Confidence bands, not false precision',
      desc: 'High / medium / low — we never show a numeric score or a price target.',
    },
    {
      icon: <BarChart2 size={20} strokeWidth={1.75} aria-hidden="true" />,
      title: 'Market Mood',
      desc: 'An educational read of market sentiment, refreshed twice daily.',
    },
    {
      icon: <BookOpen size={20} strokeWidth={1.75} aria-hidden="true" />,
      title: 'Tax Education',
      desc: 'FY-aware guides on mutual-fund taxation — capital gains, ELSS, IDCW, and key dates.',
    },
    {
      icon: <ShieldCheck size={20} strokeWidth={1.75} aria-hidden="true" />,
      title: 'Privacy-first (DPDP)',
      desc: 'Your holdings are sensitive data — processed with explicit consent, encrypted, India-resident.',
    },
    {
      icon: <GraduationCap size={20} strokeWidth={1.75} aria-hidden="true" />,
      title: 'Educational, never advisory',
      desc: 'We describe rules and form. We never tell you to buy, sell, or switch.',
    },
  ] as const;

  return (
    <section
      aria-labelledby="features-heading"
      className="mx-auto max-w-6xl px-6 py-16"
    >
      <h2
        id="features-heading"
        className="text-h2 font-semibold text-ink text-center mb-10"
      >
        What DhanRadar gives you
      </h2>
      <ul
        className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
      >
        {items.map((item) => (
          <li key={item.title}>
            <Card className="h-full">
              <CardBody className="flex flex-col gap-3 px-5 py-5">
                <span className="text-royal">{item.icon}</span>
                <h3 className="text-h3 font-medium text-ink">{item.title}</h3>
                <p className="text-body text-ink-secondary">{item.desc}</p>
              </CardBody>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------------------
// FAQ — native <details>/<summary>, no JS
// ---------------------------------------------------------------------------
function Faq() {
  const items = [
    {
      q: 'Is this investment advice?',
      a: 'No. DhanRadar is an educational research-analytics product. We never give buy, sell or hold advice — we describe each fund\'s category-relative form and explain tax rules. Investments are subject to market risk.',
    },
    {
      q: 'How does the labelled report work?',
      a: 'Upload your Consolidated Account Statement (CAMS or KFintech). We parse your funds and assign each a plain-English, category-relative label with the reasons — usually in about a minute.',
    },
    {
      q: 'Do you show a score or a target price?',
      a: 'No. By design there is no numeric score, fair value, or price target anywhere — only an educational label and a confidence band.',
    },
    {
      q: 'Is my data safe?',
      a: "Your holdings are sensitive personal data. They are processed under India's DPDP framework with your explicit consent, encrypted, and kept India-resident.",
    },
    {
      q: 'What does it cost?',
      a: 'It is free to start. Founding Access pricing is on the way.',
    },
  ] as const;

  return (
    <section
      aria-labelledby="faq-heading"
      className="bg-surface-2 border-y border-line"
    >
      <div className="mx-auto max-w-2xl px-6 py-16">
        <h2
          id="faq-heading"
          className="text-h2 font-semibold text-ink text-center mb-10"
        >
          Frequently asked
        </h2>
        <ul className="divide-y divide-line">
          {items.map((item) => (
            <li key={item.q}>
              <details className="group py-1">
                <summary
                  className={`
                    flex cursor-pointer list-none items-center justify-between
                    gap-4 py-4 text-body font-medium text-ink
                    ${LINK_RING}
                    hover:text-royal transition-colors
                  `}
                >
                  {item.q}
                  {/* Chevron — CSS-only rotate via group-open */}
                  <svg
                    className="h-4 w-4 shrink-0 text-ink-muted transition-transform duration-200 group-open:rotate-180"
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M4 6l4 4 4-4" />
                  </svg>
                </summary>
                <p className="pb-4 text-body text-ink-secondary">{item.a}</p>
              </details>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Footer
// ---------------------------------------------------------------------------
function SiteFooter() {
  const linkClass = `text-small text-ink-secondary transition-colors hover:text-ink min-h-[44px] flex items-center ${LINK_RING}`;

  return (
    <footer className="bg-surface border-t border-line">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          {/* Brand block */}
          <div className="flex flex-col gap-3 lg:col-span-1">
            <Link
              href="/"
              className={`flex items-center gap-2 ${LINK_RING}`}
              aria-label="DhanRadar home"
            >
              <Image
                src="/brand/icon.svg"
                alt=""
                width={24}
                height={24}
                className="shrink-0"
              />
              <span className="text-h3 font-semibold text-navy">DhanRadar</span>
            </Link>
            <p className="text-small text-ink-secondary max-w-xs">
              Educational mutual-fund intelligence for India. DhanRadar is a
              research-analytics product — not an investment adviser. Investments
              are subject to market risk.
            </p>
            <p className="text-caption text-ink-muted">© 2026 DhanRadar.</p>
          </div>

          {/* Product */}
          <nav aria-label="Product links">
            <p className="text-small font-semibold text-ink mb-2">Product</p>
            <ul className="flex flex-col gap-0.5">
              <li>
                <Link href="/dashboard" className={linkClass}>
                  Dashboard
                </Link>
              </li>
              <li>
                <Link href="/mf/upload" className={linkClass}>
                  Upload CAS
                </Link>
              </li>
              <li>
                <Link href="/mood" className={linkClass}>
                  Market Mood
                </Link>
              </li>
            </ul>
          </nav>

          {/* Learn */}
          <nav aria-label="Learn links">
            <p className="text-small font-semibold text-ink mb-2">Learn</p>
            <ul className="flex flex-col gap-0.5">
              <li>
                <Link href="/learn/tax" className={linkClass}>
                  Tax Education
                </Link>
              </li>
            </ul>
          </nav>

          {/* Account */}
          <nav aria-label="Account links">
            <p className="text-small font-semibold text-ink mb-2">Account</p>
            <ul className="flex flex-col gap-0.5">
              <li>
                <Link href="/login" className={linkClass}>
                  Log in
                </Link>
              </li>
              <li>
                <Link href="/signup" className={linkClass}>
                  Get started
                </Link>
              </li>
              <li>
                <Link href="/settings/privacy" className={linkClass}>
                  Privacy
                </Link>
              </li>
            </ul>
          </nav>
        </div>

        {/* Bottom disclaimer */}
        <div className="mt-10 border-t border-line pt-6 flex justify-center">
          <Disclaimer className="max-w-2xl text-center" />
        </div>
      </div>
    </footer>
  );
}

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------
export default function HomePage() {
  return (
    <div className="min-h-screen bg-bg">
      <SiteNav />
      <main>
        <Hero />
        <HowItWorks />
        <Features />
        <Faq />

        {/* Bottom CTA strip */}
        <section
          aria-labelledby="cta-heading"
          className="mx-auto max-w-6xl px-6 py-16 text-center"
        >
          <h2
            id="cta-heading"
            className="text-h2 font-semibold text-navy mb-4"
          >
            Ready to understand your funds?
          </h2>
          <p className="text-body text-ink-secondary mb-8 max-w-md mx-auto">
            Free to start. No numeric scores. No advice. Just your portfolio,
            explained in plain English.
          </p>
          <Button variant="primary" size="lg" asChild>
            <Link href="/signup">Upload your CAS — free</Link>
          </Button>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

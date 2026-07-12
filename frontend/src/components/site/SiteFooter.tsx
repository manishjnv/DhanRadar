/**
 * SiteFooter — the single, shared public footer.
 *
 * Source of truth for the footer on every PUBLIC page: the landing page,
 * /pricing, /methodology, and the anonymous branch of <MaybeShell>. Carries the
 * standing SEBI <Disclaimer/> so every public surface renders it
 * (non-negotiable #9).
 *
 * Plain server-compatible component (no hooks) so it renders inside both Server
 * Components (landing, /pricing) and Client Components (MaybeShell).
 *
 * Add or rename a public footer destination in ONE place — COLUMNS below.
 *
 * Compliance: pure navigation chrome + the standing disclaimer — no labels,
 * scores, or advisory copy. The brand line states the non-advisory boundary.
 */

import Link from 'next/link';
import Image from 'next/image';
import { Disclaimer } from '@/components/ui/Disclaimer';
import { cn } from '@/lib/cn';

const LINK_RING =
  'rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40';

// Canonical public footer columns — every entry points to an existing route.
const COLUMNS = [
  {
    heading: 'Product',
    links: [
      { href: '/mf/explore', label: 'Explore Funds' },
      { href: '/mf/portfolio', label: 'Upload CAS' },
      { href: '/mood', label: 'Market Mood' },
      { href: '/calculators', label: 'Calculators' },
      { href: '/pricing', label: 'Pricing' },
    ],
  },
  {
    heading: 'Learn',
    links: [
      { href: '/methodology', label: 'Methodology' },
      { href: '/learn/tax', label: 'Tax Education' },
      { href: '/learn/concepts', label: 'Investing Basics' },
    ],
  },
  {
    heading: 'Account',
    links: [
      { href: '/login', label: 'Log in' },
      { href: '/signup', label: 'Get started' },
      { href: '/settings/privacy', label: 'Privacy' },
    ],
  },
] as const;

export function SiteFooter() {
  const linkClass = cn(
    'flex min-h-[44px] items-center text-small text-ink-secondary transition-colors hover:text-ink',
    LINK_RING,
  );

  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {/* Brand block */}
          <div className="flex flex-col gap-3 lg:col-span-1">
            <Link
              href="/"
              className={cn('flex items-center gap-2', LINK_RING)}
              aria-label="DhanRadar home"
            >
              <Image src="/brand/icon.svg" alt="" width={24} height={24} className="shrink-0" />
              <span className="flex flex-col leading-none">
                <span className="text-h3 font-semibold text-navy">DhanRadar</span>
                <span className="mt-0.5 font-serif text-caption italic text-ink-muted">
                  Your Investment Radar
                </span>
              </span>
            </Link>
            <p className="max-w-xs text-small text-ink-secondary">
              Educational mutual-fund intelligence for India. DhanRadar is a
              research-analytics product — not an investment adviser. Mutual fund
              investments are subject to market risk.
            </p>
            <p className="text-caption text-ink-muted">© 2026 DhanRadar.</p>
          </div>

          {/* Link columns */}
          {COLUMNS.map((col) => (
            <nav key={col.heading} aria-label={`${col.heading} links`}>
              <p className="mb-2 text-small font-semibold text-ink">{col.heading}</p>
              <ul className="flex flex-col gap-0.5">
                {col.links.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href} className={linkClass}>
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        {/* Standing SEBI disclaimer — rendered on every public surface */}
        <div className="mt-6 flex justify-center border-t border-line pt-6">
          <Disclaimer className="max-w-2xl text-center" />
        </div>
      </div>
    </footer>
  );
}

export default SiteFooter;

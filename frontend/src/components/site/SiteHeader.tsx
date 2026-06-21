'use client';

/**
 * SiteHeader — the single, shared public navigation header.
 *
 * Source of truth for the top nav on every PUBLIC page: the landing page,
 * /pricing, /methodology, and the anonymous branch of <MaybeShell> (used by
 * /mood, /mf/explore, /mf/fund/[isin], /learn/*). Rendering it everywhere keeps
 * the public chrome identical across the whole logged-out surface, on web AND
 * mobile.
 *
 * Add or rename a public nav destination in ONE place — PUBLIC_NAV_LINKS below.
 *
 * Mobile: the centre links collapse into an accessible hamburger menu (the
 * landing page previously hid them with no fallback, leaving phone visitors with
 * no nav). The menu closes on route change, on Escape, and on backdrop click.
 *
 * Compliance: pure navigation chrome — no labels, scores, or advisory copy.
 */

import * as React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { Menu, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';

const LINK_RING =
  'rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40';

// Canonical public nav links — every entry points to an existing public route.
// Exported so the authenticated shell (AppShell) can surface the SAME public
// destinations in its top bar for logged-in users on public pages, keeping one
// source of truth for the public nav.
export const PUBLIC_NAV_LINKS = [
  { href: '/mf/explore', label: 'Explore Funds' },
  { href: '/methodology', label: 'Methodology' },
  { href: '/mood', label: 'Market Mood' },
  { href: '/learn/tax', label: 'Tax Education' },
  { href: '/pricing', label: 'Pricing' },
] as const;

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(href + '/');
}

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);

  // Close the mobile menu whenever the route changes.
  React.useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Close on Escape while the mobile menu is open.
  React.useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur-sm">
      <nav
        aria-label="Main navigation"
        className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6"
      >
        {/* Brand */}
        <Link
          href="/"
          className={cn('flex items-center gap-2', LINK_RING)}
          aria-label="DhanRadar home"
        >
          {/* Decorative icon; the wordmark provides the accessible name */}
          <Image src="/brand/icon.svg" alt="" width={26} height={26} className="shrink-0" />
          <span className="text-h3 font-semibold text-navy">DhanRadar</span>
        </Link>

        {/* Centre links — desktop */}
        <div className="hidden items-center gap-1 md:flex">
          {PUBLIC_NAV_LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              aria-current={isActive(pathname, l.href) ? 'page' : undefined}
              className={cn(
                'flex min-h-[44px] items-center px-3 py-2 text-small transition-colors',
                LINK_RING,
                isActive(pathname, l.href)
                  ? 'font-medium text-royal'
                  : 'text-ink-secondary hover:text-ink',
              )}
            >
              {l.label}
            </Link>
          ))}
        </div>

        {/* Right actions — desktop CTAs */}
        <div className="hidden items-center gap-2 md:flex">
          <Button variant="outline" size="sm" asChild>
            <Link href="/login">Log in</Link>
          </Button>
          <Button variant="primary" size="sm" asChild>
            <Link href="/signup">Get started — free</Link>
          </Button>
        </div>

        {/* Hamburger — mobile only */}
        <button
          type="button"
          className={cn(
            'flex min-h-[44px] min-w-[44px] items-center justify-center rounded-md text-ink-secondary md:hidden',
            'hover:bg-surface-2 hover:text-ink',
            LINK_RING,
          )}
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
          aria-controls="site-mobile-menu"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? (
            <X size={20} strokeWidth={2} aria-hidden="true" />
          ) : (
            <Menu size={20} strokeWidth={2} aria-hidden="true" />
          )}
        </button>
      </nav>

      {/* Mobile menu panel */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 top-0 z-20 bg-black/30 md:hidden"
            aria-hidden="true"
            onClick={() => setOpen(false)}
          />
          <div
            id="site-mobile-menu"
            className="relative z-30 border-t border-line bg-surface md:hidden"
          >
            <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-3">
              {PUBLIC_NAV_LINKS.map((l) => (
                <Link
                  key={l.href}
                  href={l.href}
                  aria-current={isActive(pathname, l.href) ? 'page' : undefined}
                  className={cn(
                    'flex min-h-[44px] items-center rounded-md px-3 text-body transition-colors',
                    LINK_RING,
                    isActive(pathname, l.href)
                      ? 'bg-royal/10 font-medium text-royal'
                      : 'text-ink-secondary hover:bg-surface-2 hover:text-ink',
                  )}
                >
                  {l.label}
                </Link>
              ))}
              <div className="mt-2 flex flex-col gap-2 border-t border-line pt-3">
                <Button variant="outline" size="sm" asChild>
                  <Link href="/login">Log in</Link>
                </Button>
                <Button variant="primary" size="sm" asChild>
                  <Link href="/signup">Get started — free</Link>
                </Button>
              </div>
            </div>
          </div>
        </>
      )}
    </header>
  );
}

export default SiteHeader;

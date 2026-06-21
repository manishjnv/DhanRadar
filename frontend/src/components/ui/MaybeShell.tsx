'use client';

/**
 * MaybeShell — renders public page content INSIDE the authenticated AppShell
 * (left sidebar) for logged-in users, and as a STANDALONE public page (the
 * shared <SiteHeader/> + <SiteFooter/>, no sidebar) for anonymous visitors and
 * crawlers.
 *
 * Why: the public, crawlable pages (`/mood`, `/learn/tax/*`, `/learn/concepts/*`)
 * live outside the
 * `(app)` route group, so a logged-in user clicking them in the sidebar would
 * lose the nav. This keeps the shell consistent in-app WITHOUT auth-gating the
 * page — SSR / first render is always the standalone branch (useMe has no data
 * yet), so crawlers and logged-out visitors get the clean, fast standalone page;
 * the sidebar only appears client-side once `useMe` confirms a session (a small,
 * intentional hydration swap for logged-in users).
 *
 * Pages pass ONLY their inner content as children — NOT a page header and NOT
 * the standing <Disclaimer/> (this component / AppShell provide those). The
 * contextual <DisclosureBundle/> next to the content stays in the children.
 *
 * `maxWidth` controls the content column: `'default'` (max-w-2xl) suits prose /
 * single-record pages; `'wide'` (max-w-6xl) suits data tables like the Fund
 * Explorer that need horizontal room.
 */

import * as React from 'react';

import { AppShell } from '@/components/ui/AppShell';
import { SiteHeader } from '@/components/site/SiteHeader';
import { SiteFooter } from '@/components/site/SiteFooter';
import { UserMenu } from '@/features/auth/UserMenu';
import { useMe } from '@/features/auth/api';
import { cn } from '@/lib/cn';

export function MaybeShell({
  children,
  maxWidth = 'default',
}: {
  children: React.ReactNode;
  maxWidth?: 'default' | 'wide';
}) {
  const { data: user } = useMe();
  const widthClass = maxWidth === 'wide' ? 'max-w-6xl' : 'max-w-2xl';

  // Logged in → render within the app shell so the left nav stays consistent.
  if (user) {
    return (
      <AppShell userSlot={<UserMenu />}>
        <div className={cn('mx-auto', widthClass)}>{children}</div>
      </AppShell>
    );
  }

  // Anonymous / crawler / initial render → standalone public chrome.
  // SiteHeader + SiteFooter are the shared, site-wide public chrome (identical
  // on the landing page, /pricing, /methodology, and every MaybeShell page) so
  // the logged-out experience is consistent on web and mobile. SiteFooter
  // carries the standing <Disclaimer/>.
  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <SiteHeader />
      <main className={cn('mx-auto w-full flex-1 px-4 py-8 sm:px-6', widthClass)}>
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}

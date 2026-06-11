'use client';

/**
 * MaybeShell — renders public page content INSIDE the authenticated AppShell
 * (left sidebar) for logged-in users, and as a STANDALONE public page (own
 * header + footer, no sidebar) for anonymous visitors and crawlers.
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
 */

import * as React from 'react';
import Link from 'next/link';

import { AppShell } from '@/components/ui/AppShell';
import { Button } from '@/components/ui/Button';
import { Disclaimer } from '@/components/ui/Disclaimer';
import { UserMenu } from '@/features/auth/UserMenu';
import { useMe } from '@/features/auth/api';

export function MaybeShell({ children }: { children: React.ReactNode }) {
  const { data: user } = useMe();

  // Logged in → render within the app shell so the left nav stays consistent.
  if (user) {
    return (
      <AppShell userSlot={<UserMenu />}>
        <div className="mx-auto max-w-2xl">{children}</div>
      </AppShell>
    );
  }

  // Anonymous / crawler / initial render → standalone public chrome.
  return (
    <div className="min-h-screen bg-bg">
      <header className="flex items-center justify-between border-b border-line bg-surface px-4 py-3">
        <Link href="/" className="flex items-center gap-2.5">
          {/* Decorative mark; the wordmark provides the accessible name. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/icon.svg" alt="" width={26} height={26} className="shrink-0" />
          <span className="text-h3 font-medium text-navy">DhanRadar</span>
        </Link>
        <Button variant="outline" size="sm" asChild>
          <Link href="/dashboard">Open app</Link>
        </Button>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-8">
        {children}
        {/* Standing site-wide line — the standalone page has no AppShell footer. */}
        <footer className="mt-10 border-t border-line pt-4">
          <Disclaimer className="text-center" />
        </footer>
      </main>
    </div>
  );
}

'use client';

/**
 * AuthGuard — client-side gate for the authenticated `(app)` route group.
 *
 * The cookie session is the source of truth: we probe GET /auth/me (which
 * triggers apiClient's one silent refresh on 401). If still anonymous, we
 * redirect to /login carrying a `next` param so the user lands back where
 * they were. This is a UX gate, NOT the security boundary — every protected
 * endpoint is independently enforced server-side (RequireTier / cookie auth).
 */

import * as React from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useMe } from './api';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: user, isLoading, isError } = useMe();

  React.useEffect(() => {
    if (isLoading) return;

    // 1. Anonymous user → /login (primary guard, runs first).
    if (isError || !user) {
      const next = encodeURIComponent(pathname || '/dashboard');
      router.replace(`/login?next=${next}`);
      return;
    }

    // 2. Cold-start: authenticated but risk_profile not yet set → /onboarding.
    //    Guard against redirect loops: skip when already on /onboarding.
    if (user.risk_profile == null && pathname !== '/onboarding') {
      router.replace('/onboarding');
      return;
    }

    // 3. Completed: risk_profile IS set but the user is sitting on /onboarding
    //    (post-submit refetch race, back-button, or a bookmark) → /dashboard.
    //    Without this the onboarding quiz shows a second time and sticks.
    if (user.risk_profile != null && pathname === '/onboarding') {
      router.replace('/dashboard');
    }
  }, [isLoading, isError, user, pathname, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <div
          className="h-6 w-6 animate-spin rounded-full border-2 border-line border-t-royal"
          role="status"
          aria-label="Checking your session"
        />
      </div>
    );
  }

  // Redirecting to /login — render nothing rather than flashing protected chrome.
  if (isError || !user) return null;

  // Redirecting to /onboarding — suppress children until navigation fires.
  if (user.risk_profile == null && pathname !== '/onboarding') return null;

  // Redirecting a completed user off /onboarding — suppress the quiz flash.
  if (user.risk_profile != null && pathname === '/onboarding') return null;

  return <>{children}</>;
}

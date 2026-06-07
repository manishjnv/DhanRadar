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
    if (!isLoading && (isError || !user)) {
      const next = encodeURIComponent(pathname || '/dashboard');
      router.replace(`/login?next=${next}`);
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

  // Redirecting — render nothing rather than flashing protected chrome.
  if (isError || !user) return null;

  return <>{children}</>;
}

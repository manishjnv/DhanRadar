/**
 * Signal route — server component shell.
 *
 * Fetches hasCAS server-side so the client component never needs an
 * auth-gated existence check. Uses INTERNAL_API_URL (Docker network)
 * + __Host-access cookie forwarded to the backend.
 *
 * SEBI: no advisory verbs, no numeric DhanRadar score in DOM.
 * force-dynamic: page is user-specific — never statically rendered.
 */

import { Suspense } from 'react';
import { cookies } from 'next/headers';
import { SignalPage } from '@/features/signal/SignalPage';

export const dynamic = 'force-dynamic';

async function getHasCAS(): Promise<boolean> {
  const cookieStore = cookies();
  const access = cookieStore.get('__Host-access');
  if (!access?.value) return false;

  const apiBase =
    (process.env.INTERNAL_API_URL ?? 'http://fastapi:8000').replace(/\/$/, '');

  try {
    // Was /dashboard/portfolio-summary — that path never existed (RCA: this
    // check always returned false). Mirrors useLatestPortfolio()
    // (features/mf/api.ts) — a raw fetch, not the hook, since this is a
    // server component and hooks require client render context. 200 = has
    // a portfolio, 404 = cold-start (no portfolio yet).
    const res = await fetch(`${apiBase}/api/v1/mf/portfolio/latest`, {
      headers: { Cookie: `__Host-access=${access.value}` },
      cache: 'no-store',
    });
    return res.ok;
  } catch (_e) {
    // Backend unreachable during build or test — safe default
    return false;
  }
}

export default async function SignalPageRoute() {
  const hasCAS = await getHasCAS();

  return (
    <Suspense fallback={null}>
      <SignalPage hasCAS={hasCAS} />
    </Suspense>
  );
}

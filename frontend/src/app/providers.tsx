'use client';

import { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';

// Whether to run the MSW mock layer. Explicit flag wins (enabled/disabled);
// otherwise default ON in development so `npm run dev` works with no backend
// and no env file, and OFF in production builds. NODE_ENV is identical on the
// server and client, so the initial `ready` state below can't cause a
// hydration mismatch.
function mockingEnabled(): boolean {
  const flag = process.env.NEXT_PUBLIC_API_MOCKING;
  if (flag === 'enabled') return true;
  if (flag === 'disabled') return false;
  return process.env.NODE_ENV === 'development';
}

// Module-level guard: React StrictMode runs effects twice in dev, which would
// call worker.start() on an already-enabled network ("cannot configure an
// already enabled network"). Start at most once per page load.
let mocksStarted = false;

async function initMocks() {
  if (!mockingEnabled() || mocksStarted) return;
  mocksStarted = true;
  const { worker } = await import('@/mocks/browser');
  await worker.start({ onUnhandledRequest: 'bypass' });
}

// The mock layer must NEVER be able to brick the app. If worker.start() rejects
// (stale/"waiting" service-worker registration, integrity warning, transient SW
// lifecycle stall…) or hangs, we still render the app rather than trapping the
// user on the loading screen forever. A short timeout is the backstop; the error,
// if any, is surfaced to the console for diagnosis.
const MOCK_START_TIMEOUT_MS = 3000;

export function Providers({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(!mockingEnabled());

  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
          },
        },
      }),
  );

  useEffect(() => {
    if (!mockingEnabled()) return;

    let done = false;
    const finish = () => {
      if (!done) {
        done = true;
        setReady(true);
      }
    };

    initMocks()
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.error('[mocks] MSW failed to start; continuing without it:', err);
      })
      .finally(finish);

    // Backstop: if start() neither resolves nor rejects, don't hang the UI.
    const timer = setTimeout(finish, MOCK_START_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, []);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg text-ink-muted text-small">
        Starting development mocks…
      </div>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  );
}

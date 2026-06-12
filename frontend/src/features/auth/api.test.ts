/**
 * Auth API test — exercises the raw apiClient and TanStack Query hooks against
 * the MSW node server.
 *
 * - GET /auth/me (underpinning of useMe())
 * - POST /auth/totp/login (useTotpLogin — success + 401)
 *
 * The MSW server default state is mockLoggedIn = true; resetHandlers() (called
 * by afterEach in setup.ts) restores that default between tests.
 */
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import * as React from 'react';
import { api } from '@/lib/apiClient';
import { server } from '@/mocks/server';
import { queryKeys } from '@/lib/queryKeys';
import type { MeEnvelope } from './types';
import { useTotpLogin } from './api';

// ---------------------------------------------------------------------------
// Wrapper factory — each test gets a fresh QueryClient to avoid cache leakage.
// ---------------------------------------------------------------------------
function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  }
  return { qc, Wrapper };
}

describe('auth api — GET /auth/me', () => {
  it('returns an envelope with a user object', async () => {
    const result = await api.get<MeEnvelope>('/auth/me');
    expect(result).toHaveProperty('user');
    expect(result.user).toHaveProperty('id');
    expect(result.user).toHaveProperty('email');
    expect(result.user).toHaveProperty('tier');
  });

  it('user email matches demo account', async () => {
    const result = await api.get<MeEnvelope>('/auth/me');
    expect(result.user.email).toBe('demo@dhanradar.in');
  });

  it('user tier is a recognised value', async () => {
    const result = await api.get<MeEnvelope>('/auth/me');
    const validTiers = ['anonymous', 'free', 'pro', 'pro_plus', 'founder_lifetime'];
    expect(validTiers).toContain(result.user.tier);
  });
});

describe('useTotpLogin — POST /auth/totp/login', () => {
  it('success: seeds the me cache with the returned user', async () => {
    const { qc, Wrapper } = makeWrapper();
    const { result } = renderHook(() => useTotpLogin(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.mutateAsync).toBeDefined());

    await result.current.mutateAsync({ email: 'demo@dhanradar.in', code: '123456' });

    // The onSuccess handler must have seeded the me cache.
    const cached = qc.getQueryData<{ id: string; email: string }>(queryKeys.auth.me());
    expect(cached).not.toBeNull();
    expect(cached?.email).toBe('demo@dhanradar.in');
  });

  it('401: mutation rejects and me cache is NOT seeded', async () => {
    // Override the default handler to return a 401 for this test.
    server.use(
      http.post('/api/v1/auth/totp/login', () =>
        HttpResponse.json(
          {
            type: 'about:blank',
            title: 'Unauthorized',
            status: 401,
            detail: 'invalid_credentials',
            request_id: 'mock-401',
          },
          { status: 401, headers: { 'Content-Type': 'application/problem+json' } },
        ),
      ),
    );

    const { qc, Wrapper } = makeWrapper();
    const { result } = renderHook(() => useTotpLogin(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.mutateAsync).toBeDefined());

    await expect(
      result.current.mutateAsync({ email: 'demo@dhanradar.in', code: '000000' }),
    ).rejects.toMatchObject({ problem: { status: 401, detail: 'invalid_credentials' } });

    // me cache must remain empty — onSuccess must NOT have fired.
    const cached = qc.getQueryData(queryKeys.auth.me());
    expect(cached).toBeUndefined();
  });
});

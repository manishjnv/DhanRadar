/**
 * AuthGuard cold-start routing tests.
 *
 * Cold-start: a user with risk_profile: null on any pathname other than
 * '/onboarding' should be redirected to '/onboarding'.
 *
 * No-redirect: a user with risk_profile already set should NOT be redirected
 * to '/onboarding'.
 *
 * Already on /onboarding: a null-profile user already on '/onboarding'
 * must NOT trigger a redirect loop.
 *
 * Mocks: useMe and next/navigation, following the AppShell.test.tsx pattern.
 */
import * as React from 'react';
import { render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthGuard } from './AuthGuard';

// ---------------------------------------------------------------------------
// Hoisted mocks — vi.mock is hoisted before imports by vitest
// ---------------------------------------------------------------------------

// We control the return value of useMe per test via mockReturnValue below
const mockUseMe = vi.fn();

vi.mock('./api', () => ({
  useMe: () => mockUseMe(),
}));

const mockReplace = vi.fn();
let mockPathname = '/dashboard';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => mockPathname,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function renderGuard(children = <div data-testid="child">Protected</div>) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthGuard>{children}</AuthGuard>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mockReplace.mockClear();
  mockPathname = '/dashboard';
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('AuthGuard — cold-start routing', () => {
  it('redirects to /onboarding when user has risk_profile: null on /dashboard', async () => {
    mockUseMe.mockReturnValue({
      data: { id: '1', email: 'a@b.com', tier: 'free', totp_verified: false, risk_profile: null, dpdp_consent_version: null },
      isLoading: false,
      isError: false,
    });

    renderGuard();

    await waitFor(() =>
      expect(mockReplace).toHaveBeenCalledWith('/onboarding'),
    );
  });

  it('does NOT redirect when user has risk_profile set to "moderate"', async () => {
    mockUseMe.mockReturnValue({
      data: { id: '1', email: 'a@b.com', tier: 'free', totp_verified: false, risk_profile: 'moderate', dpdp_consent_version: null },
      isLoading: false,
      isError: false,
    });

    renderGuard();

    // Give the effect a tick to potentially fire
    await new Promise((r) => setTimeout(r, 50));

    expect(mockReplace).not.toHaveBeenCalledWith('/onboarding');
  });

  it('redirects a COMPLETED user (risk_profile set) away from /onboarding to /dashboard', async () => {
    // The post-submit double-visit bug: a user whose profile is already set must
    // never sit on /onboarding (no re-entry / no second showing of the quiz).
    mockPathname = '/onboarding';
    mockUseMe.mockReturnValue({
      data: { id: '1', email: 'a@b.com', tier: 'free', totp_verified: false, risk_profile: 'aggressive', dpdp_consent_version: null },
      isLoading: false,
      isError: false,
    });

    renderGuard();

    await waitFor(() =>
      expect(mockReplace).toHaveBeenCalledWith('/dashboard'),
    );
  });

  it('does NOT redirect when already on /onboarding (no loop)', async () => {
    mockPathname = '/onboarding';
    mockUseMe.mockReturnValue({
      data: { id: '1', email: 'a@b.com', tier: 'free', totp_verified: false, risk_profile: null, dpdp_consent_version: null },
      isLoading: false,
      isError: false,
    });

    renderGuard();

    await new Promise((r) => setTimeout(r, 50));

    expect(mockReplace).not.toHaveBeenCalledWith('/onboarding');
  });

  it('does NOT redirect while isLoading is true', async () => {
    mockUseMe.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    renderGuard();

    await new Promise((r) => setTimeout(r, 50));

    expect(mockReplace).not.toHaveBeenCalled();
  });

  it('redirects anonymous user to /login (existing guard preserved)', async () => {
    mockUseMe.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    renderGuard();

    await waitFor(() =>
      expect(mockReplace).toHaveBeenCalledWith(
        expect.stringContaining('/login'),
      ),
    );
    expect(mockReplace).not.toHaveBeenCalledWith('/onboarding');
  });
});

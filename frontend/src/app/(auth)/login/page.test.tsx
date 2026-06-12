/**
 * Login page — focused component tests covering TOTP mode behaviours.
 *
 * Strategy: mock useLogin, useTotpLogin, and next/navigation (same pattern as
 * AuthGuard.cold-start.test.tsx). We render LoginPage which wraps LoginForm in
 * Suspense; in jsdom Suspense resolves synchronously for non-lazy children.
 *
 * Coverage:
 *  1. Switching to TOTP mode shows the code input.
 *  2. Typing 6 digits fires exactly one TOTP mutate call.
 *  3. A 401 response shows the inline error and clears the input.
 *  4. Switching back to password mode restores the password input.
 *
 * Full-page router navigation is not tested here — that requires the Next.js
 * test runner. Routing behaviour is covered by the useTotpLogin hook test
 * (onSuccess seeds cache → caller navigates).
 */

import * as React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiError } from '@/lib/apiClient';

// ---------------------------------------------------------------------------
// Hoisted mocks — vi.mock is hoisted before imports by vitest
// ---------------------------------------------------------------------------

const mockLoginMutate = vi.fn();
const mockTotpLoginMutate = vi.fn();

vi.mock('@/features/auth/api', () => ({
  useLogin: () => ({ mutate: mockLoginMutate, isPending: false }),
  useTotpLogin: () => ({ mutate: mockTotpLoginMutate, isPending: false }),
}));

const mockRouterReplace = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockRouterReplace }),
  useSearchParams: () => ({
    get: (_key: string) => null,
  }),
}));

// ---------------------------------------------------------------------------
// Import AFTER mocks are declared
// ---------------------------------------------------------------------------
import LoginPage from './page';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function renderLoginPage() {
  return render(<LoginPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('LoginPage — TOTP mode', () => {
  it('switching to TOTP mode shows the authenticator code input', async () => {
    renderLoginPage();

    const switchBtn = screen.getByRole('button', {
      name: /sign in with an authenticator code instead/i,
    });
    await userEvent.click(switchBtn);

    expect(screen.getByLabelText(/authenticator code/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });

  it('entering 6 digits with a valid email fires exactly one TOTP mutate', async () => {
    renderLoginPage();

    // Switch to TOTP mode
    await userEvent.click(
      screen.getByRole('button', { name: /sign in with an authenticator code instead/i }),
    );

    // Fill email
    const emailInput = screen.getByLabelText(/email/i);
    await userEvent.clear(emailInput);
    await userEvent.type(emailInput, 'demo@dhanradar.in');

    // Make the mutate resolve immediately (no-op success)
    mockTotpLoginMutate.mockImplementation(
      (_creds: unknown, opts: { onSuccess?: () => void }) => {
        opts?.onSuccess?.();
      },
    );

    // Simulate entering a 6-digit code via fireEvent.change (bypasses the
    // char-by-char approach; our onChange strips non-digits and caps at 6).
    const codeInput = screen.getByLabelText(/authenticator code/i);
    fireEvent.change(codeInput, { target: { value: '123456' } });

    await waitFor(() => {
      expect(mockTotpLoginMutate).toHaveBeenCalledTimes(1);
      expect(mockTotpLoginMutate).toHaveBeenCalledWith(
        { email: 'demo@dhanradar.in', code: '123456' },
        expect.any(Object),
      );
    });
  });

  it('401 response shows the inline error and clears the code input', async () => {
    renderLoginPage();

    await userEvent.click(
      screen.getByRole('button', { name: /sign in with an authenticator code instead/i }),
    );

    const emailInput = screen.getByLabelText(/email/i);
    await userEvent.clear(emailInput);
    await userEvent.type(emailInput, 'demo@dhanradar.in');

    // Make the mutate call invoke onError with a 401 ApiError.
    mockTotpLoginMutate.mockImplementation(
      (_creds: unknown, opts: { onError?: (err: unknown) => void }) => {
        opts?.onError?.(
          new ApiError({
            type: 'about:blank',
            title: 'Unauthorized',
            status: 401,
            detail: 'invalid_credentials',
            request_id: 'mock-401',
          }),
        );
      },
    );

    const codeInput = screen.getByLabelText(/authenticator code/i);
    fireEvent.change(codeInput, { target: { value: '000000' } });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/invalid code/i);
    });

    // Code input must be cleared on 401.
    expect((codeInput as HTMLInputElement).value).toBe('');
  });

  it('switching back to password mode restores the password input', async () => {
    renderLoginPage();

    await userEvent.click(
      screen.getByRole('button', { name: /sign in with an authenticator code instead/i }),
    );
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: /use password instead/i }),
    );
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });
});

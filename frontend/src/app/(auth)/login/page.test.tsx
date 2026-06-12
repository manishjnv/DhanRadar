/**
 * Login page — focused component tests covering email_otp mode behaviours.
 *
 * Strategy: mock useLogin, useRequestEmailOtp, useEmailOtpLogin, and
 * next/navigation (same pattern as AuthGuard.cold-start.test.tsx). We render
 * LoginPage which wraps LoginForm in Suspense; in jsdom Suspense resolves
 * synchronously for non-lazy children.
 *
 * Coverage:
 *  1. Switcher button renders in password mode with the new label; clicking switches.
 *  2. email_otp phase 1: invalid email blocks the request.
 *  3. email_otp phase 1: valid email fires POST /email-otp/request → phase 2.
 *  4. Auto-submit fires /email-otp/login when 6th digit typed; success redirects.
 *  5. 401 response shows the generic error and clears the code input.
 *  6. 503 on request shows the unavailable message.
 *  7. Resend disabled initially; countdown shown; enabled after 60s.
 *  8. Switching back to password mode restores the password input.
 */

import * as React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiError } from '@/lib/apiClient';

// ---------------------------------------------------------------------------
// Hoisted mocks — vi.mock is hoisted before imports by vitest
// ---------------------------------------------------------------------------

const mockLoginMutate = vi.fn();
const mockRequestOtpMutate = vi.fn();
const mockEmailOtpLoginMutate = vi.fn();

vi.mock('@/features/auth/api', () => ({
  useLogin: () => ({ mutate: mockLoginMutate, isPending: false }),
  useRequestEmailOtp: () => ({ mutate: mockRequestOtpMutate, isPending: false }),
  useEmailOtpLogin: () => ({ mutate: mockEmailOtpLoginMutate, isPending: false }),
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
  vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// Helper: advance to email_otp mode and optionally to code phase
// ---------------------------------------------------------------------------
async function switchToEmailOtpMode() {
  const switchBtn = screen.getByRole('button', { name: /sign in with email code/i });
  await userEvent.click(switchBtn);
}

async function advanceToCodePhase(email = 'demo@dhanradar.in') {
  await switchToEmailOtpMode();

  // Fill a valid email
  const emailInput = screen.getByLabelText(/email/i);
  await userEvent.clear(emailInput);
  await userEvent.type(emailInput, email);

  // Make request mutation succeed immediately
  mockRequestOtpMutate.mockImplementation(
    (_body: unknown, opts: { onSuccess?: () => void }) => {
      opts?.onSuccess?.();
    },
  );

  const requestBtn = screen.getByRole('button', { name: /email me a login code/i });
  await userEvent.click(requestBtn);

  await waitFor(() => {
    expect(screen.getByLabelText(/email code/i)).toBeInTheDocument();
  });
}

// ---------------------------------------------------------------------------
// Tests — password mode baseline
// ---------------------------------------------------------------------------
describe('LoginPage — password mode', () => {
  it('renders the email code switcher button with the new label', () => {
    renderLoginPage();
    expect(
      screen.getByRole('button', { name: /sign in with email code/i }),
    ).toBeInTheDocument();
  });

  it('clicking the switcher switches to email_otp mode', async () => {
    renderLoginPage();
    await switchToEmailOtpMode();
    expect(
      screen.getByRole('button', { name: /email me a login code/i }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests — email_otp phase 1 (request)
// ---------------------------------------------------------------------------
describe('LoginPage — email_otp phase 1 (request)', () => {
  it('invalid email blocks the OTP request and shows email field error', async () => {
    renderLoginPage();
    await switchToEmailOtpMode();

    // Leave email empty, click "Email me a login code"
    const requestBtn = screen.getByRole('button', { name: /email me a login code/i });
    await userEvent.click(requestBtn);

    await waitFor(() => {
      // RHF should show the email required error
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });

    // Request mutation must NOT have fired
    expect(mockRequestOtpMutate).not.toHaveBeenCalled();
  });

  it('valid email fires POST /email-otp/request and advances to phase 2', async () => {
    renderLoginPage();
    await advanceToCodePhase();

    expect(mockRequestOtpMutate).toHaveBeenCalledTimes(1);
    expect(mockRequestOtpMutate).toHaveBeenCalledWith(
      { email: 'demo@dhanradar.in' },
      expect.any(Object),
    );
    // Phase 2 indicator
    expect(screen.getByText(/we sent a 6-digit code/i)).toBeInTheDocument();
  });

  it('503 on request shows the unavailable message', async () => {
    renderLoginPage();
    await switchToEmailOtpMode();

    const emailInput = screen.getByLabelText(/email/i);
    await userEvent.clear(emailInput);
    await userEvent.type(emailInput, 'demo@dhanradar.in');

    mockRequestOtpMutate.mockImplementation(
      (_body: unknown, opts: { onError?: (err: unknown) => void }) => {
        opts?.onError?.(
          new ApiError({
            type: 'about:blank',
            title: 'Service Unavailable',
            status: 503,
            detail: 'email_otp_not_configured',
            request_id: 'mock-503',
          }),
        );
      },
    );

    await userEvent.click(screen.getByRole('button', { name: /email me a login code/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        /email code login is not available right now/i,
      );
    });
  });
});

// ---------------------------------------------------------------------------
// Tests — email_otp phase 2 (code input + auto-submit)
// ---------------------------------------------------------------------------
describe('LoginPage — email_otp phase 2 (code)', () => {
  it('auto-submit fires /email-otp/login when 6th digit typed; success redirects', async () => {
    renderLoginPage();
    await advanceToCodePhase();

    mockEmailOtpLoginMutate.mockImplementation(
      (_creds: unknown, opts: { onSuccess?: () => void }) => {
        opts?.onSuccess?.();
      },
    );

    const codeInput = screen.getByLabelText(/email code/i);
    fireEvent.change(codeInput, { target: { value: '123456' } });

    await waitFor(() => {
      expect(mockEmailOtpLoginMutate).toHaveBeenCalledTimes(1);
      expect(mockEmailOtpLoginMutate).toHaveBeenCalledWith(
        { email: 'demo@dhanradar.in', code: '123456' },
        expect.any(Object),
      );
    });

    // Redirect — same idiom as password login test
    expect(mockRouterReplace).toHaveBeenCalledWith('/dashboard');
  });

  it('401 shows the generic error and clears the code input', async () => {
    renderLoginPage();
    await advanceToCodePhase();

    mockEmailOtpLoginMutate.mockImplementation(
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

    const codeInput = screen.getByLabelText(/email code/i);
    fireEvent.change(codeInput, { target: { value: '000000' } });

    await waitFor(() => {
      expect(screen.getByText(/invalid or expired code/i)).toBeInTheDocument();
    });

    // Code input must be cleared on 401
    expect((codeInput as HTMLInputElement).value).toBe('');
  });

  it('manual Log in button with 6 digits fires POST /email-otp/login', async () => {
    renderLoginPage();
    await advanceToCodePhase();

    mockEmailOtpLoginMutate.mockImplementation(
      (_creds: unknown, opts: { onSuccess?: () => void }) => {
        opts?.onSuccess?.();
      },
    );

    // Type 6 digits using userEvent (no auto-submit: mock returns void synchronously
    // so we can override it below; but here we just use the submit button directly)
    const codeInput = screen.getByLabelText(/email code/i);
    await userEvent.type(codeInput, '654321');

    // Clear any auto-submit call so we can verify the button click independently
    mockEmailOtpLoginMutate.mockClear();
    mockEmailOtpLoginMutate.mockImplementation(
      (_creds: unknown, opts: { onSuccess?: () => void }) => {
        opts?.onSuccess?.();
      },
    );

    const submitBtn = screen.getByRole('button', { name: /^log in$/i });
    await userEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockEmailOtpLoginMutate).toHaveBeenCalledWith(
        { email: 'demo@dhanradar.in', code: '654321' },
        expect.any(Object),
      );
    });
    expect(mockRouterReplace).toHaveBeenCalledWith('/dashboard');
  });

  it('manual submit with <6 digits shows the enter-6-digit error and does NOT fire the request', async () => {
    renderLoginPage();
    await advanceToCodePhase();

    // Type only 3 digits
    const codeInput = screen.getByLabelText(/email code/i);
    await userEvent.type(codeInput, '123');

    mockEmailOtpLoginMutate.mockClear();

    const submitBtn = screen.getByRole('button', { name: /^log in$/i });
    await userEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/enter the 6-digit code from your email/i),
      ).toBeInTheDocument();
    });

    expect(mockEmailOtpLoginMutate).not.toHaveBeenCalled();
  });

  it('403 account_deletion_pending shows its message', async () => {
    renderLoginPage();
    await advanceToCodePhase();

    mockEmailOtpLoginMutate.mockImplementation(
      (_creds: unknown, opts: { onError?: (err: unknown) => void }) => {
        opts?.onError?.(
          new ApiError({
            type: 'about:blank',
            title: 'Forbidden',
            status: 403,
            detail: 'account_deletion_pending',
            request_id: 'mock-403',
          }),
        );
      },
    );

    const codeInput = screen.getByLabelText(/email code/i);
    fireEvent.change(codeInput, { target: { value: '999999' } });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        /this account has a pending deletion request/i,
      );
    });
  });
});

// ---------------------------------------------------------------------------
// Tests — resend countdown
// ---------------------------------------------------------------------------
describe('LoginPage — resend countdown', () => {
  it('resend is disabled immediately after advancing to phase 2', async () => {
    renderLoginPage();
    await advanceToCodePhase();

    const resendBtn = screen.getByRole('button', { name: /resend code/i });
    expect(resendBtn).toBeDisabled();
    // Should show countdown label like "Resend code (60s)" or "(59s)" etc.
    expect(resendBtn.textContent).toMatch(/resend code \(\d+s\)/i);
  });

  it('resend button is enabled after 60 seconds and shows plain label', async () => {
    // Install fake timers before mounting so the component's setInterval is faked.
    vi.useFakeTimers();

    renderLoginPage();

    // Navigate to email_otp mode using fireEvent (synchronous — no async overhead).
    fireEvent.click(screen.getAllByRole('button', { name: /sign in with email code/i })[0]);

    // Fill the email field.
    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: 'demo@dhanradar.in' },
    });

    // Arm the request mock.
    mockRequestOtpMutate.mockImplementation(
      (_body: unknown, opts: { onSuccess?: () => void }) => {
        opts?.onSuccess?.();
      },
    );

    // Click "Email me a login code".  handleRequestOtp calls trigger('email')
    // (a Promise), so we need to flush microtasks before the onSuccess fires.
    fireEvent.click(screen.getByRole('button', { name: /email me a login code/i }));
    await act(async () => {});   // flush microtasks (RHF validation + React state)

    // Phase 2 should be visible now.
    expect(screen.getByLabelText(/email code/i)).toBeInTheDocument();

    // Resend button starts disabled with countdown label.
    expect(screen.getByRole('button', { name: /resend code \(\d+s\)/i })).toBeDisabled();

    // Advance fake clock 61 s — all 60 interval ticks fire, countdown reaches 0.
    act(() => { vi.advanceTimersByTime(61_000); });

    // Button should now be enabled with the plain "Resend code" label.
    const resendBtn = screen.getByRole('button', { name: /^resend code$/i });
    expect(resendBtn).not.toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// Tests — back-navigation
// ---------------------------------------------------------------------------
describe('LoginPage — mode switching', () => {
  it('switching back to password mode restores the password input', async () => {
    renderLoginPage();
    await switchToEmailOtpMode();

    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: /use password instead/i }),
    );

    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });
});

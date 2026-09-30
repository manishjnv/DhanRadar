/**
 * Login page — ?reason=idle notice.
 *
 * Separate test file from page.test.tsx because that file's next/navigation
 * mock hard-codes useSearchParams().get() to always return null; duplicating
 * vi.mock('next/navigation', ...) for a single param here in its own file
 * avoids touching that shared mock.
 *
 * Covers the idle-signout contract: the login page must show a neutral,
 * non-error notice (not styled as an error) when redirected here after the
 * 15-min idle sign-out (see frontend/src/lib/useIdleSignOut.ts).
 */
import { render, screen } from '@testing-library/react';
import LoginPage from './page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams('reason=idle'),
}));

vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock('@/features/auth/api', () => ({
  useLogin: () => ({ mutate: vi.fn(), isPending: false }),
  useRequestEmailOtp: () => ({ mutate: vi.fn(), isPending: false }),
  useEmailOtpLogin: () => ({ mutate: vi.fn(), isPending: false }),
}));

describe('LoginPage ?reason=idle', () => {
  it('shows a neutral info notice, not a red error', () => {
    render(<LoginPage />);

    const notice = screen.getByText(
      'You were signed out after 15 minutes of no activity. Please sign in again.',
    );
    expect(notice).toBeInTheDocument();
    expect(notice).toHaveAttribute('role', 'status');
    expect(notice.className).not.toContain('text-red');
  });
});

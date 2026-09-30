/**
 * Privacy & consent page — "Delete my account" section tests (B79 self-service).
 *
 * Coverage: dialog opens on button click, confirming calls the deletion
 * mutation, then the page redirects to /login?notice=deletion_requested.
 */

import * as React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PrivacyConsentPage from './page';
import * as consentApi from '@/features/consent/api';
import * as authApi from '@/features/auth/api';
import type { ConsentState } from '@/features/consent/types';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const mockConsentState: ConsentState = {
  consents: {
    mf_analytics: true,
    ai_insights: true,
    portfolio_sync: true,
    behavioral_nudges: true,
    marketing: false,
    cross_border_ai: true,
    cross_border_notify: true,
  },
  consent_version: '2.1',
};

describe('PrivacyConsentPage — Delete my account', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(consentApi, 'useConsent').mockReturnValue({
      data: mockConsentState,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof consentApi.useConsent>);
    vi.spyOn(consentApi, 'useGrantConsent').mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof consentApi.useGrantConsent>);
    vi.spyOn(consentApi, 'useRevokeConsent').mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof consentApi.useRevokeConsent>);
  });

  it('renders the section with plain-language copy and a destructive button', () => {
    vi.spyOn(authApi, 'useRequestAccountDeletion').mockReturnValue({
      mutateAsync: vi.fn(),
    } as unknown as ReturnType<typeof authApi.useRequestAccountDeletion>);

    render(<PrivacyConsentPage />, { wrapper: createWrapper() });

    expect(screen.getByRole('heading', { name: 'Delete my account' })).toBeInTheDocument();
    expect(
      screen.getByText(/we will delete your account and your portfolio data/i),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete my account' })).toBeInTheDocument();
  });

  it('opens a confirm dialog, calls the deletion mutation, and redirects on confirm', async () => {
    const user = userEvent.setup();
    const mutateAsync = vi.fn().mockResolvedValue({ status: 'deletion_requested' });
    vi.spyOn(authApi, 'useRequestAccountDeletion').mockReturnValue({
      mutateAsync,
    } as unknown as ReturnType<typeof authApi.useRequestAccountDeletion>);

    const assignSpy = vi.fn();
    Object.defineProperty(window, 'location', {
      value: { assign: assignSpy },
      writable: true,
    });

    render(<PrivacyConsentPage />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Delete my account' }));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Yes, delete my account' }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith('/login?notice=deletion_requested');
    });
  });
});

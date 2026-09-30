/**
 * Cancel-deletion page — the emailed "keep my account" link.
 *
 * Coverage:
 *  1. No token in the URL → invalid message, no submit button, NO auto-POST.
 *  2. Token present → idle state does NOT auto-POST on mount either.
 *  3. Clicking "Keep my account" calls the mutation; success shows the
 *     confirmation + Sign in button.
 *  4. A 400 ApiError shows the "not valid or has expired" message.
 *  5. A non-ApiError (network) failure shows the retry state.
 */

import * as React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiError } from '@/lib/apiClient';

const mockMutate = vi.fn();
const mockRouterPush = vi.fn();

vi.mock('@/features/auth/api', () => ({
  useCancelAccountDeletion: () => ({ mutate: mockMutate, isPending: false }),
}));

let searchParamsValue: string | null = 'good-token';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockRouterPush }),
  useSearchParams: () => ({
    get: (key: string) => (key === 'token' ? searchParamsValue : null),
  }),
}));

import CancelDeletionPage from './page';

beforeEach(() => {
  vi.clearAllMocks();
  searchParamsValue = 'good-token';
});

describe('CancelDeletionPage', () => {
  it('shows an invalid message and no submit button when the token is missing (no auto-POST)', () => {
    searchParamsValue = null;
    render(<CancelDeletionPage />);

    expect(screen.getByText(/missing its confirmation code/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /keep my account/i })).not.toBeInTheDocument();
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it('never auto-submits on mount when a token IS present', () => {
    render(<CancelDeletionPage />);

    expect(screen.getByRole('button', { name: /keep my account/i })).toBeInTheDocument();
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it('clicking the button calls the mutation and success shows the confirmation + Sign in', async () => {
    const user = userEvent.setup();
    mockMutate.mockImplementation((_token: string, opts: { onSuccess?: () => void }) => {
      opts?.onSuccess?.();
    });

    render(<CancelDeletionPage />);
    await user.click(screen.getByRole('button', { name: /keep my account/i }));

    expect(mockMutate).toHaveBeenCalledWith('good-token', expect.anything());
    await waitFor(() => {
      expect(screen.getByText(/your account is safe/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('a 400 ApiError shows the not-valid-or-expired message', async () => {
    const user = userEvent.setup();
    const err = new ApiError({
      type: 'https://dhanradar.com/errors/bad_request',
      title: 'Bad Request',
      status: 400,
      request_id: 'r1',
      detail: 'invalid_or_expired_link',
    });
    mockMutate.mockImplementation((_token: string, opts: { onError?: (e: unknown) => void }) => {
      opts?.onError?.(err);
    });

    render(<CancelDeletionPage />);
    await user.click(screen.getByRole('button', { name: /keep my account/i }));

    await waitFor(() => {
      expect(screen.getByText(/not valid or has expired/i)).toBeInTheDocument();
    });
  });

  it('a network error shows the retry state', async () => {
    const user = userEvent.setup();
    mockMutate.mockImplementation((_token: string, opts: { onError?: (e: unknown) => void }) => {
      opts?.onError?.(new Error('network down'));
    });

    render(<CancelDeletionPage />);
    await user.click(screen.getByRole('button', { name: /keep my account/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
  });
});

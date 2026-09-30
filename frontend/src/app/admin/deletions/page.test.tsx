/**
 * Account deletions page — loading/empty/error/success + 409 wait-period handling.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminDeletionsPage from './page';
import * as adminApi from '@/features/admin/api';
import type { AdminDeletionsResponse } from '@/features/admin/api';
import { ApiError } from '@/lib/apiClient';

vi.mock('@/features/admin/api', async () => {
  const actual = await vi.importActual<typeof import('@/features/admin/api')>(
    '@/features/admin/api',
  );
  return {
    ...actual,
    useAdminDeletions: vi.fn(),
    useCancelDeletion: vi.fn(),
    useEraseUser: vi.fn(),
  };
});

const RESPONSE: AdminDeletionsResponse = {
  pending: [
    {
      user_id: '00000000-0000-0000-0000-000000000001',
      email: 'waiting@example.com',
      requested_at: new Date().toISOString(),
      earliest_erase_at: new Date(Date.now() + 6 * 24 * 60 * 60 * 1000).toISOString(),
      erase_by: new Date(Date.now() + 29 * 24 * 60 * 60 * 1000).toISOString(),
      status: 'waiting',
    },
    {
      user_id: '00000000-0000-0000-0000-000000000002',
      email: 'ready@example.com',
      requested_at: '2026-01-01T00:00:00Z',
      earliest_erase_at: '2026-01-08T00:00:00Z',
      erase_by: '2026-01-31T00:00:00Z',
      status: 'overdue',
    },
  ],
  recent_erasures: [
    { erased_at: '2026-09-01T00:00:00Z', rows_removed: 42, erased_by: 'founder@dhanradar.com' },
  ],
  policy: {
    erase_wait_days: 7,
    erase_due_days: 30,
    retention: [
      { label: 'Consent records', keep_days: 2922 },
      { label: 'Security logs', keep_days: 365 },
    ],
  },
  retention_job: { last_run_at: '2026-09-01T02:00:00Z', result: 'success' },
};

describe('AdminDeletionsPage', () => {
  beforeEach(() => {
    vi.mocked(adminApi.useCancelDeletion).mockReturnValue({
      mutateAsync: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useCancelDeletion>);
    vi.mocked(adminApi.useEraseUser).mockReturnValue({
      mutateAsync: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useEraseUser>);
  });

  it('shows a loading skeleton while the query is in flight', () => {
    vi.mocked(adminApi.useAdminDeletions).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useAdminDeletions>);

    render(<AdminDeletionsPage />);
    expect(screen.queryByText('Pending requests')).not.toBeInTheDocument();
  });

  it('shows an error state with retry when the query fails', () => {
    const refetch = vi.fn();
    vi.mocked(adminApi.useAdminDeletions).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    } as unknown as ReturnType<typeof adminApi.useAdminDeletions>);

    render(<AdminDeletionsPage />);
    expect(screen.getByText(/could not load account deletions/i)).toBeInTheDocument();
  });

  it('shows "No deletion requests." when pending is empty', () => {
    vi.mocked(adminApi.useAdminDeletions).mockReturnValue({
      data: { ...RESPONSE, pending: [] },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useAdminDeletions>);

    render(<AdminDeletionsPage />);
    expect(screen.getByText('No deletion requests.')).toBeInTheDocument();
  });

  it('renders summary chips, pending rows, recent erasures, and the retention policy', () => {
    vi.mocked(adminApi.useAdminDeletions).mockReturnValue({
      data: RESPONSE,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useAdminDeletions>);

    render(<AdminDeletionsPage />);

    expect(screen.getByText('waiting@example.com')).toBeInTheDocument();
    expect(screen.getByText('ready@example.com')).toBeInTheDocument();
    expect(screen.getAllByText('Overdue').length).toBeGreaterThan(0);
    expect(screen.getByText('founder@dhanradar.com')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('Consent records')).toBeInTheDocument();
    expect(screen.getByText(/last run/i)).toBeInTheDocument();
  });

  it('disables Erase permanently for a row still inside the wait period', () => {
    vi.mocked(adminApi.useAdminDeletions).mockReturnValue({
      data: RESPONSE,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useAdminDeletions>);

    render(<AdminDeletionsPage />);

    const buttons = screen.getAllByRole('button', { name: 'Erase permanently' });
    // Row order matches `pending`: [0] waiting (disabled), [1] overdue (enabled).
    expect(buttons[0]).toBeDisabled();
    expect(buttons[0]).toHaveAttribute('title', expect.stringContaining('Can erase from'));
    expect(buttons[1]).toBeEnabled();
  });

  it('shows a friendly "Can erase from" message on a 409 erasure_wait_period response', async () => {
    const user = userEvent.setup();
    const eraseMutateAsync = vi.fn().mockRejectedValue(
      new ApiError({
        type: 'about:blank',
        title: 'Conflict',
        status: 409,
        detail: 'erasure_wait_period',
        request_id: 'req-1',
        earliest_erase_at: '2026-02-05T00:00:00Z',
      }),
    );
    vi.mocked(adminApi.useEraseUser).mockReturnValue({
      mutateAsync: eraseMutateAsync,
    } as unknown as ReturnType<typeof adminApi.useEraseUser>);
    vi.mocked(adminApi.useAdminDeletions).mockReturnValue({
      data: RESPONSE,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useAdminDeletions>);

    render(<AdminDeletionsPage />);

    const buttons = screen.getAllByRole('button', { name: 'Erase permanently' });
    await user.click(buttons[1]); // the overdue/enabled row
    await screen.findByRole('dialog');

    const dialogButtons = screen.getAllByRole('button', { name: 'Erase permanently' });
    await user.type(screen.getByLabelText(/type/i), 'ready@example.com');
    await user.click(dialogButtons[dialogButtons.length - 1]);

    await waitFor(() => {
      expect(screen.getByText(/^Can erase from \d/i)).toBeInTheDocument();
    });
  });
});

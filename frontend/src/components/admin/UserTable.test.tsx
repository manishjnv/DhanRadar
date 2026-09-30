/**
 * UserTable — deletion-requested badge + Cancel/Erase actions (B79 admin UI).
 */

import * as React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UserTable } from './UserTable';
import * as adminApi from '@/features/admin/api';
import type { AdminUserRow } from '@/features/admin/api';

const activeUser: AdminUserRow = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'active@example.com',
  display_name: 'active',
  tier: 'free',
  status: 'active',
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
  deletion_requested_at: null,
};

const pendingUser: AdminUserRow = {
  id: '00000000-0000-0000-0000-000000000002',
  email: 'pending@example.com',
  display_name: 'pending',
  tier: 'free',
  status: 'active',
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
  deletion_requested_at: '2026-09-29T00:00:00Z',
};

describe('UserTable — deletion-requested', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(adminApi, 'useSuspendUser').mockReturnValue({
      mutateAsync: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useSuspendUser>);
    vi.spyOn(adminApi, 'useUnsuspendUser').mockReturnValue({
      mutateAsync: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useUnsuspendUser>);
    vi.spyOn(adminApi, 'useResetUserAccess').mockReturnValue({
      mutateAsync: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useResetUserAccess>);
  });

  it('shows an amber "Deletion requested" badge instead of the normal status badge', () => {
    const cancelMutateAsync = vi.fn();
    const eraseMutateAsync = vi.fn();
    vi.spyOn(adminApi, 'useCancelDeletion').mockReturnValue({
      mutateAsync: cancelMutateAsync,
    } as unknown as ReturnType<typeof adminApi.useCancelDeletion>);
    vi.spyOn(adminApi, 'useEraseUser').mockReturnValue({
      mutateAsync: eraseMutateAsync,
    } as unknown as ReturnType<typeof adminApi.useEraseUser>);

    render(<UserTable users={[activeUser, pendingUser]} onView={vi.fn()} />);

    expect(screen.getByText(/deletion requested/i)).toBeInTheDocument();
    // Only the pending user gets Cancel Request / Erase Permanently.
    expect(screen.getByRole('button', { name: 'Cancel Request' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Erase Permanently' })).toBeInTheDocument();
    // Active (non-pending) user still shows the normal Suspend action.
    expect(screen.getByRole('button', { name: 'Suspend' })).toBeInTheDocument();
  });

  it('Cancel Request opens a confirm dialog and calls the cancel-deletion mutation', async () => {
    const user = userEvent.setup();
    const cancelMutateAsync = vi.fn().mockResolvedValue({ ok: true, status: 'active' });
    vi.spyOn(adminApi, 'useCancelDeletion').mockReturnValue({
      mutateAsync: cancelMutateAsync,
    } as unknown as ReturnType<typeof adminApi.useCancelDeletion>);
    vi.spyOn(adminApi, 'useEraseUser').mockReturnValue({
      mutateAsync: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useEraseUser>);

    render(<UserTable users={[pendingUser]} onView={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Cancel Request' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toBeInTheDocument();

    // Two buttons now share the name (row action + dialog confirm).
    const dialogConfirm = screen.getAllByRole('button', { name: 'Cancel Request' }).slice(-1)[0];
    await user.click(dialogConfirm);

    await waitFor(() => {
      expect(cancelMutateAsync).toHaveBeenCalledWith(pendingUser.id);
    });
  });

  it('Erase Permanently requires typing the email before it is enabled, then calls the erase mutation with an Idempotency-Key', async () => {
    const user = userEvent.setup();
    const eraseMutateAsync = vi.fn().mockResolvedValue({ ok: true, counts: { 'auth.users': 1 } });
    vi.spyOn(adminApi, 'useCancelDeletion').mockReturnValue({
      mutateAsync: vi.fn(),
    } as unknown as ReturnType<typeof adminApi.useCancelDeletion>);
    vi.spyOn(adminApi, 'useEraseUser').mockReturnValue({
      mutateAsync: eraseMutateAsync,
    } as unknown as ReturnType<typeof adminApi.useEraseUser>);

    render(<UserTable users={[pendingUser]} onView={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Erase Permanently' }));
    await screen.findByRole('dialog');

    // Two buttons now share the name (row action + dialog confirm) — the
    // dialog's confirm button (last one) is disabled until the email matches.
    const dialogConfirm = screen.getAllByRole('button', { name: 'Erase Permanently' }).slice(-1)[0];
    expect(dialogConfirm).toBeDisabled();

    await user.type(screen.getByLabelText(/type/i), pendingUser.email);
    expect(dialogConfirm).toBeEnabled();

    await user.click(dialogConfirm);

    await waitFor(() => {
      expect(eraseMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ id: pendingUser.id }),
      );
    });
    const call = eraseMutateAsync.mock.calls[0][0];
    expect(typeof call.idempotencyKey).toBe('string');
    expect(call.idempotencyKey.length).toBeGreaterThan(0);
  });
});

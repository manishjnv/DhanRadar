/**
 * UserMenu logout test — clicking "Log out" fires the logout mutation and
 * lands the user on the public homepage ('/'), not /login.
 *
 * Mocks: ./api and next/navigation, following AuthGuard.cold-start.test.tsx.
 */
import * as React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { UserMenu } from './UserMenu';

// mutate immediately settles, like the real mutation after the round trip
const mockMutate = vi.fn(
  (_vars: unknown, opts?: { onSettled?: () => void }) => opts?.onSettled?.(),
);

vi.mock('./api', () => ({
  useMe: () => ({
    data: {
      id: '1',
      email: 'a@b.com',
      tier: 'free',
      totp_verified: false,
      risk_profile: 'moderate',
      dpdp_consent_version: null,
    },
  }),
  useLogout: () => ({ mutate: mockMutate, isPending: false }),
}));

const mockReplace = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn(), prefetch: vi.fn() }),
}));

describe('UserMenu — logout', () => {
  it('clicking Log out fires the logout mutation and lands on the homepage', () => {
    render(<UserMenu />);

    fireEvent.click(screen.getByRole('button', { name: /log out/i }));

    expect(mockMutate).toHaveBeenCalled();
    expect(mockReplace).toHaveBeenCalledWith('/');
  });
});

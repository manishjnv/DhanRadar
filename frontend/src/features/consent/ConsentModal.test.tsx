/**
 * ConsentModal test — the "Grant & continue" action is gated on the required
 * "I consent" checkbox, and granting drives the grant mutation + onGranted.
 */
import * as React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConsentModal } from './ConsentModal';

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('ConsentModal', () => {
  it('renders nothing when closed', () => {
    renderWithClient(
      <ConsentModal open={false} purposes={['mf_analytics']} onGranted={() => {}} onCancel={() => {}} />,
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('disables grant until consent is checked, then grants and calls onGranted', async () => {
    const user = userEvent.setup();
    const onGranted = vi.fn();
    renderWithClient(
      <ConsentModal open purposes={['mf_analytics']} onGranted={onGranted} onCancel={() => {}} />,
    );

    const grantBtn = screen.getByRole('button', { name: /grant & continue/i });
    expect(grantBtn).toBeDisabled();

    await user.click(screen.getByRole('checkbox'));
    expect(grantBtn).toBeEnabled();

    await user.click(grantBtn);
    await waitFor(() => expect(onGranted).toHaveBeenCalledTimes(1));
  });

  it('Escape fires onCancel', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    renderWithClient(
      <ConsentModal open purposes={['mf_analytics']} onGranted={() => {}} onCancel={onCancel} />,
    );
    await user.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalled();
  });
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import MfuUatConsolePage from './page';
import { api, ApiError } from '@/lib/apiClient';

vi.mock('@/lib/apiClient', async () => {
  const actual = await vi.importActual<typeof import('@/lib/apiClient')>('@/lib/apiClient');
  return {
    ...actual,
    api: {
      get: vi.fn(),
      post: vi.fn(),
      putH: vi.fn(),
    },
  };
});

const PING_OK = {
  enabled: true,
  base_url_ok: true,
  configured: {
    entity_id: true,
    login_user: true,
    login_password: true,
    aes_key: true,
    aes_iv: true,
  },
  token_cached: true,
  token_ttl_s: 79200,
  cooldown_s: null,
};

function mockRoute(path: string, handler: () => unknown) {
  vi.mocked(api.get).mockImplementation(async (p: string) => {
    if (p.startsWith(path)) return handler();
    throw new Error(`unexpected GET ${p}`);
  });
}

describe('MfuUatConsolePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the status checklist from ping', async () => {
    mockRoute('/admin/mfu-uat/ping', () => PING_OK);
    vi.mocked(api.get).mockImplementation(async (p: string) => {
      if (p.startsWith('/admin/mfu-uat/ping')) return PING_OK;
      if (p.startsWith('/admin/mfu-uat/api-log')) return [];
      if (p.startsWith('/admin/mf-txn/provider')) throw new ApiError({ type: 'x', title: 'Not Found', status: 404, request_id: '' });
      throw new Error(`unexpected GET ${p}`);
    });

    render(<MfuUatConsolePage />);

    expect(await screen.findByText('Switched on')).toBeTruthy();
    expect(screen.getByText('Logged in — yes — 22 h left')).toBeTruthy();
  });

  it('humanizes a COOLDOWN login error', async () => {
    vi.mocked(api.get).mockImplementation(async (p: string) => {
      if (p.startsWith('/admin/mfu-uat/ping')) return PING_OK;
      if (p.startsWith('/admin/mfu-uat/api-log')) return [];
      throw new ApiError({ type: 'x', title: 'Not Found', status: 404, request_id: '' });
    });
    vi.mocked(api.post).mockRejectedValue(
      new ApiError({
        type: 'x',
        title: 'Too Many Requests',
        status: 429,
        request_id: '',
        error_code: 'COOLDOWN',
        error_msg: 'Please wait',
      }),
    );

    const { default: userEvent } = await import('@testing-library/user-event');
    render(<MfuUatConsolePage />);

    const btn = await screen.findByRole('button', { name: 'Log in' });
    await userEvent.click(btn);

    expect(
      await screen.findByText('The last login failed. Please wait a few minutes (safety rule).'),
    ).toBeTruthy();
  });

  it('shows a not-ready provider option as disabled with its note', async () => {
    vi.mocked(api.get).mockImplementation(async (p: string) => {
      if (p.startsWith('/admin/mfu-uat/ping')) return PING_OK;
      if (p.startsWith('/admin/mfu-uat/api-log')) return [];
      if (p.startsWith('/admin/mf-txn/provider')) {
        return {
          provider: 'bse',
          provider_label: 'BSE StAR MF',
          source: 'default',
          default: 'bse',
          options: [
            { id: 'bse', label: 'BSE StAR MF', ready: true, note: '' },
            { id: 'mfu', label: 'MF Utility', ready: false, note: 'Not ready yet — MF Utility orders come in a later phase.' },
          ],
        };
      }
      throw new Error(`unexpected GET ${p}`);
    });

    render(<MfuUatConsolePage />);

    const mfuBtn = await screen.findByRole('button', { name: 'Use MF Utility' });
    expect(mfuBtn.hasAttribute('disabled')).toBe(true);
    expect(screen.getByText('Not ready yet — MF Utility orders come in a later phase.')).toBeTruthy();
  });

  it('shows the empty state when the call log has no rows', async () => {
    vi.mocked(api.get).mockImplementation(async (p: string) => {
      if (p.startsWith('/admin/mfu-uat/ping')) return PING_OK;
      if (p.startsWith('/admin/mfu-uat/api-log')) return [];
      throw new ApiError({ type: 'x', title: 'Not Found', status: 404, request_id: '' });
    });

    render(<MfuUatConsolePage />);

    expect(await screen.findByText('No MF Utility calls yet')).toBeTruthy();
  });
});

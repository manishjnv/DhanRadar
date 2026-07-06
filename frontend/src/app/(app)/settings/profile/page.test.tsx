/**
 * Customer Profile page tests.
 *
 * Coverage:
 *  - All 14 tabs render and are switchable.
 *  - Privacy & Consent tab (REAL) shows 7 purposes and calls grant/revoke mutations on toggle.
 *  - At least 2-3 dummy tabs render illustrative content + "Illustrative — coming soon" badge.
 */

import * as React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { toast } from 'sonner';
import ProfilePage from './page';
import * as authApi from '@/features/auth/api';
import * as consentApi from '@/features/consent/api';
import type { AuthUser } from '@/features/auth/types';
import type { ConsentState } from '@/features/consent/types';

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Test utilities
// ---------------------------------------------------------------------------

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

interface WrapperProps {
  children: React.ReactNode;
}

function createWrapper() {
  const queryClient = createTestQueryClient();
  return function Wrapper({ children }: WrapperProps) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const mockUser: AuthUser = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'test@example.com',
  tier: 'free',
  totp_verified: false,
  risk_profile: null,
  dpdp_consent_version: null,
  is_admin: false,
};

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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ProfilePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Tab navigation', () => {
    it('renders all 14 tabs', async () => {
      vi.spyOn(authApi, 'useMe').mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof authApi.useMe>);

      vi.spyOn(consentApi, 'useConsent').mockReturnValue({
        data: mockConsentState,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof consentApi.useConsent>);

      render(<ProfilePage />, { wrapper: createWrapper() });

      const expectedTabs = [
        'Overview',
        'Personal',
        'Investment',
        'Risk',
        'Privacy & Consent',
        'Accounts',
        'Documents',
        'Security',
        'Notifications',
        'Preferences',
        'Connected',
        'Activity',
        'Data & Privacy',
        'Support',
      ];

      // All tabs are present
      const tablist = screen.getByRole('tablist', { name: /profile sections/i });
      const tabs = within(tablist).getAllByRole('tab');
      expect(tabs).toHaveLength(14);

      expectedTabs.forEach((label) => {
        expect(
          within(tablist).getByRole('tab', { name: label }),
        ).toBeInTheDocument();
      });
    });

    it('switches between tabs when clicked', async () => {
      const user = userEvent.setup();
      vi.spyOn(authApi, 'useMe').mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof authApi.useMe>);

      vi.spyOn(consentApi, 'useConsent').mockReturnValue({
        data: mockConsentState,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof consentApi.useConsent>);

      render(<ProfilePage />, { wrapper: createWrapper() });

      // Start on Overview tab (default)
      const overviewTab = screen.getByRole('tab', { name: 'Overview' });
      expect(overviewTab).toHaveAttribute('aria-selected', 'true');
      expect(overviewTab).toHaveAttribute('aria-current', 'page');
      expect(screen.getByText(/profile at a glance/i)).toBeInTheDocument();

      // Switch to Personal tab
      const personalTab = screen.getByRole('tab', { name: 'Personal' });
      await user.click(personalTab);
      await waitFor(() => {
        expect(personalTab).toHaveAttribute('aria-selected', 'true');
        expect(personalTab).toHaveAttribute('aria-current', 'page');
      });
      expect(screen.getByText(/identity/i)).toBeInTheDocument();
      expect(screen.queryByText(/profile at a glance/i)).not.toBeInTheDocument();

      // Switch to Privacy & Consent tab
      const privacyTab = screen.getByRole('tab', { name: 'Privacy & Consent' });
      await user.click(privacyTab);
      await waitFor(() => {
        expect(privacyTab).toHaveAttribute('aria-selected', 'true');
        expect(privacyTab).toHaveAttribute('aria-current', 'page');
      });
      expect(screen.getByText(/\d+ of 7 permissions are on/i)).toBeInTheDocument();
      expect(screen.queryByText(/identity/i)).not.toBeInTheDocument();

      // Switch to Security tab
      const securityTab = screen.getByRole('tab', { name: 'Security' });
      await user.click(securityTab);
      await waitFor(() => {
        expect(securityTab).toHaveAttribute('aria-selected', 'true');
        expect(securityTab).toHaveAttribute('aria-current', 'page');
      });
      expect(screen.getByText(/security score/i)).toBeInTheDocument();
      expect(screen.queryByText(/\d+ of 7 permissions are on/i)).not.toBeInTheDocument();
    });
  });

  describe('Privacy & Consent tab (REAL)', () => {
    it('renders all 7 real consent purposes', async () => {
      const user = userEvent.setup();
      vi.spyOn(authApi, 'useMe').mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof authApi.useMe>);

      vi.spyOn(consentApi, 'useConsent').mockReturnValue({
        data: mockConsentState,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof consentApi.useConsent>);

      render(<ProfilePage />, { wrapper: createWrapper() });

      // Navigate to Privacy & Consent tab
      const privacyTab = screen.getByRole('tab', { name: 'Privacy & Consent' });
      await user.click(privacyTab);

      await waitFor(() => {
        expect(screen.getByText(/\d+ of 7 permissions are on/i)).toBeInTheDocument();
      });

      // Verify all 7 purposes are present (using their exact titles from purposeCopy,
      // grouped under plain-English section headings)
      expect(screen.getByText(/read your mutual fund holdings/i)).toBeInTheDocument();
      expect(screen.getByText(/write ai notes about your portfolio/i)).toBeInTheDocument();
      expect(screen.getByText(/save a copy of your portfolio/i)).toBeInTheDocument();
      expect(screen.getByText(/send you portfolio reminders/i)).toBeInTheDocument();
      expect(screen.getByText(/send you tips and product updates/i)).toBeInTheDocument();
      expect(screen.getByText(/let ai run on servers outside india/i)).toBeInTheDocument();
      expect(screen.getByText(/let alerts be sent from outside india/i)).toBeInTheDocument();

      // Verify toggle states match mock data — DOM order follows CONSENT_GROUPS:
      // [mf_analytics, portfolio_sync, ai_insights, cross_border_ai, behavioral_nudges, marketing, cross_border_notify]
      // Queried by accessible name (not role) — each Toggle's aria-label starts with
      // "Turn on:"/"Turn off:", which uniquely targets the 7 consent controls.
      const toggles = screen.getAllByLabelText(/^turn (on|off):/i);
      expect(toggles).toHaveLength(7);

      // mf_analytics: true
      expect(toggles[0]).toHaveAttribute('aria-checked', 'true');
      // portfolio_sync: true
      expect(toggles[1]).toHaveAttribute('aria-checked', 'true');
      // ai_insights: true
      expect(toggles[2]).toHaveAttribute('aria-checked', 'true');
      // cross_border_ai: true
      expect(toggles[3]).toHaveAttribute('aria-checked', 'true');
      // behavioral_nudges: true
      expect(toggles[4]).toHaveAttribute('aria-checked', 'true');
      // marketing: false
      expect(toggles[5]).toHaveAttribute('aria-checked', 'false');
      // cross_border_notify: true
      expect(toggles[6]).toHaveAttribute('aria-checked', 'true');
    });

    it('calls grant mutation when toggling consent ON', async () => {
      const user = userEvent.setup();
      const mockGrant = vi.fn();

      vi.spyOn(authApi, 'useMe').mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof authApi.useMe>);

      vi.spyOn(consentApi, 'useConsent').mockReturnValue({
        data: mockConsentState,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof consentApi.useConsent>);

      vi.spyOn(consentApi, 'useGrantConsent').mockReturnValue({
        mutate: mockGrant,
        isPending: false,
      } as unknown as ReturnType<typeof consentApi.useGrantConsent>);

      vi.spyOn(consentApi, 'useRevokeConsent').mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
      } as unknown as ReturnType<typeof consentApi.useRevokeConsent>);

      render(<ProfilePage />, { wrapper: createWrapper() });

      // Navigate to Privacy & Consent tab
      const privacyTab = screen.getByRole('tab', { name: 'Privacy & Consent' });
      await user.click(privacyTab);

      await waitFor(() => {
        expect(screen.getByText(/\d+ of 7 permissions are on/i)).toBeInTheDocument();
      });

      // Find the marketing toggle (currently OFF in mock data) — 6th in grouped DOM order
      const toggles = screen.getAllByLabelText(/^turn (on|off):/i);
      const marketingToggle = toggles[5];

      expect(marketingToggle).toHaveAttribute('aria-checked', 'false');

      // Click to grant consent
      await user.click(marketingToggle);

      await waitFor(() => {
        expect(mockGrant).toHaveBeenCalledWith(
          { purposes: ['marketing'] },
          expect.any(Object),
        );
      });
    });

    it('calls revoke mutation when toggling consent OFF', async () => {
      const user = userEvent.setup();
      const mockRevoke = vi.fn();

      vi.spyOn(authApi, 'useMe').mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof authApi.useMe>);

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
        mutate: mockRevoke,
        isPending: false,
      } as unknown as ReturnType<typeof consentApi.useRevokeConsent>);

      render(<ProfilePage />, { wrapper: createWrapper() });

      // Navigate to Privacy & Consent tab
      const privacyTab = screen.getByRole('tab', { name: 'Privacy & Consent' });
      await user.click(privacyTab);

      await waitFor(() => {
        expect(screen.getByText(/\d+ of 7 permissions are on/i)).toBeInTheDocument();
      });

      // Find the mf_analytics toggle (currently ON in mock data) — 1st in grouped DOM order
      const toggles = screen.getAllByLabelText(/^turn (on|off):/i);
      const analyticsToggle = toggles[0];

      expect(analyticsToggle).toHaveAttribute('aria-checked', 'true');

      // Click to revoke consent
      await user.click(analyticsToggle);

      await waitFor(() => {
        expect(mockRevoke).toHaveBeenCalledWith(
          { purposes: ['mf_analytics'] },
          expect.any(Object),
        );
      });
    });

    it('shows active consent count correctly', async () => {
      const user = userEvent.setup();
      vi.spyOn(authApi, 'useMe').mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof authApi.useMe>);

      vi.spyOn(consentApi, 'useConsent').mockReturnValue({
        data: mockConsentState,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof consentApi.useConsent>);

      render(<ProfilePage />, { wrapper: createWrapper() });

      // Navigate to Privacy & Consent tab
      const privacyTab = screen.getByRole('tab', { name: 'Privacy & Consent' });
      await user.click(privacyTab);

      await waitFor(() => {
        expect(screen.getByText(/\d+ of 7 permissions are on/i)).toBeInTheDocument();
      });

      // mockConsentState has 6 true consents out of 7 total
      expect(screen.getByText(/6 of 7 permissions are on/i)).toBeInTheDocument();
    });
  });

  describe('Dummy tabs with illustrative badges', () => {
    beforeEach(() => {
      vi.spyOn(authApi, 'useMe').mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof authApi.useMe>);

      vi.spyOn(consentApi, 'useConsent').mockReturnValue({
        data: mockConsentState,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof consentApi.useConsent>);
    });

    it('Overview tab shows illustrative badge', async () => {
      const user = userEvent.setup();
      render(<ProfilePage />, { wrapper: createWrapper() });

      // Overview is default tab
      await waitFor(() => {
        expect(screen.getByText(/profile at a glance/i)).toBeInTheDocument();
      });

      // Illustrative badge is present
      expect(screen.getByText(/illustrative — coming soon/i)).toBeInTheDocument();

      // Sample illustrative content is present
      expect(screen.getByText(/profile at a glance/i)).toBeInTheDocument();
      expect(screen.getByText(/completion checklist/i)).toBeInTheDocument();
      expect(screen.getByText(/sample user/i)).toBeInTheDocument();
    });

    it('Documents tab shows illustrative badge and document list', async () => {
      const user = userEvent.setup();
      render(<ProfilePage />, { wrapper: createWrapper() });

      // Navigate to Documents tab
      const documentsTab = screen.getByRole('tab', { name: 'Documents' });
      await user.click(documentsTab);

      await waitFor(() => {
        expect(screen.getByText(/document vault/i)).toBeInTheDocument();
      });

      // Illustrative badge is present
      expect(screen.getByText(/illustrative — coming soon/i)).toBeInTheDocument();

      // Document vault heading is present
      expect(screen.getByText(/document vault/i)).toBeInTheDocument();

      // Sample documents are present
      expect(screen.getByText(/pan card/i)).toBeInTheDocument();
      expect(screen.getByText(/aadhaar/i)).toBeInTheDocument();
      expect(screen.getByText(/ckyc record/i)).toBeInTheDocument();
      expect(screen.getByText(/consent pdfs/i)).toBeInTheDocument();
      expect(screen.getByText(/risk report/i)).toBeInTheDocument();
      expect(screen.getByText(/cas uploads/i)).toBeInTheDocument();
    });

    it('Security tab shows illustrative badge and security features', async () => {
      const user = userEvent.setup();
      render(<ProfilePage />, { wrapper: createWrapper() });

      // Navigate to Security tab
      const securityTab = screen.getByRole('tab', { name: 'Security' });
      await user.click(securityTab);

      await waitFor(() => {
        expect(screen.getByText(/security score/i)).toBeInTheDocument();
      });

      // Illustrative badge is present
      expect(screen.getByText(/illustrative — coming soon/i)).toBeInTheDocument();

      // Security score section is present
      expect(screen.getByText(/security score/i)).toBeInTheDocument();
      expect(screen.getByText(/strong protection/i)).toBeInTheDocument();

      // Sample security features are present
      expect(screen.getByText(/two-factor authentication/i)).toBeInTheDocument();
      expect(screen.getByText(/biometric login/i)).toBeInTheDocument();
      expect(screen.getByText(/passkeys/i)).toBeInTheDocument();
      expect(screen.getByText(/devices & sessions/i)).toBeInTheDocument();
    });

    it('Support tab shows illustrative badge and future features', async () => {
      const user = userEvent.setup();
      render(<ProfilePage />, { wrapper: createWrapper() });

      // Navigate to Support tab
      const supportTab = screen.getByRole('tab', { name: 'Support' });
      await user.click(supportTab);

      await waitFor(() => {
        expect(screen.getByText(/your relationship manager/i)).toBeInTheDocument();
      });

      // Illustrative badge is present
      expect(screen.getByText(/illustrative — coming soon/i)).toBeInTheDocument();

      // Relationship manager section is present
      expect(screen.getByText(/your relationship manager/i)).toBeInTheDocument();
      expect(screen.getByText(/priya krishnan/i)).toBeInTheDocument();

      // Help & tickets section is present
      expect(screen.getByText(/help & tickets/i)).toBeInTheDocument();
      expect(screen.getByText(/support tickets/i)).toBeInTheDocument();

      // Future features section heading is present
      const futureHeading = screen.getAllByText(/coming soon/i).find((el) => el.tagName.toLowerCase() === 'h3');
      expect(futureHeading).toBeInTheDocument();
      
      // Sample future features are present
      expect(screen.getByText(/family/i)).toBeInTheDocument();
      expect(screen.getByText(/joint/i)).toBeInTheDocument();
    });
  });

  describe('Profile hero', () => {
    it('displays user email and tier from useMe()', async () => {
      vi.spyOn(authApi, 'useMe').mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof authApi.useMe>);

      vi.spyOn(consentApi, 'useConsent').mockReturnValue({
        data: mockConsentState,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof consentApi.useConsent>);

      render(<ProfilePage />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.getByText('test@example.com')).toBeInTheDocument();
      });

      expect(screen.getByText(/free/i)).toBeInTheDocument();
    });

    it('displays tier labels correctly for different tiers', async () => {
      const proUser: AuthUser = {
        ...mockUser,
        tier: 'pro',
      };

      vi.spyOn(authApi, 'useMe').mockReturnValue({
        data: proUser,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof authApi.useMe>);

      vi.spyOn(consentApi, 'useConsent').mockReturnValue({
        data: mockConsentState,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof consentApi.useConsent>);

      render(<ProfilePage />, { wrapper: createWrapper() });

      await waitFor(() => {
        // Look for the tier badge specifically, not just any text containing "pro"
        const tierBadge = screen.getByText((content, element) => {
          return element?.tagName.toLowerCase() === 'span' && 
                 element.className.includes('rounded-full') && 
                 /^pro$/i.test(content);
        });
        expect(tierBadge).toBeInTheDocument();
      });
    });

    it('computes initials from email', async () => {
      vi.spyOn(authApi, 'useMe').mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof authApi.useMe>);

      vi.spyOn(consentApi, 'useConsent').mockReturnValue({
        data: mockConsentState,
        isLoading: false,
        isError: false,
      } as ReturnType<typeof consentApi.useConsent>);

      render(<ProfilePage />, { wrapper: createWrapper() });

      // Email is test@example.com, so initials should be TE
      await waitFor(() => {
        expect(screen.getByText('TE')).toBeInTheDocument();
      });
    });
  });
});

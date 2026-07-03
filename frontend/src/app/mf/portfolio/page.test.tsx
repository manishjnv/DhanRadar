/**
 * Portfolio page — UploadFAB + header toolbar vitest tests.
 *
 * Covers:
 *  1. Header toolbar renders Refresh / Generate Report / Export (Auto Sync disabled).
 *  2. Page renders exactly ONE persistent upload affordance (the FAB, not the old 5-button bar).
 *  3. Clicking the FAB opens the upload popover (file input + password field present).
 *  4. Typing a password + picking a file calls casUpload.start with (file, password).
 *  5. Popover shows progress state when phase=processing.
 *  6. Popover shows error + retry + password field when phase=error.
 *  7. Escape closes the popover when idle.
 *  8. X button closes the popover when idle.
 */

import * as React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ---------------------------------------------------------------------------
// Mock dependencies so the test is pure-unit (no real API calls).
// ---------------------------------------------------------------------------

// Mock the whole api module — only useLatestPortfolio is needed by page.tsx directly.
vi.mock('@/features/mf/api', () => ({
  useLatestPortfolio: vi.fn(() => ({ data: { portfolio_id: 'pid-test' } })),
  useUploadCas: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useCasStatus: vi.fn(() => ({ data: undefined, isLoading: false, timedOut: false })),
}));

// Mock useCasUpload so we can control its return value per test.
const mockCasUpload = {
  phase: 'idle' as const,
  progressPct: 0,
  statusLabel: '',
  errorMessage: null as string | null,
  errorCode: null as string | null,
  estimatedSeconds: null as number | null,
  start: vi.fn(),
  reset: vi.fn(),
};

vi.mock('@/features/mf/cas-upload', () => ({
  useCasUpload: vi.fn(() => mockCasUpload),
}));

// Mock all sections so the page renders without real API calls.
vi.mock('@/components/mf/portfolio/sections', () => ({
  EmptyHero: () => <div data-testid="empty-hero" />,
  BenefitsGrid: () => <div />,
  AutoSyncBanner: () => <div />,
  HeroSection: () => <div />,
  VsMarketSection: () => <div />,
  HealthSection: () => <div />,
  ActionSection: () => <div />,
  DmmiSection: () => <div />,
  AllocSection: () => <div />,
  GoalSection: () => <div />,
  PerfSection: () => <div />,
  HoldingsSection: () => <div />,
  TopPerfSection: () => <div />,
  UnderReviewSection: () => <div />,
  OverlapSection: () => <div />,
  DivSection: () => <div />,
  RiskSection: () => <div />,
  CostSection: () => <div />,
  AmcSection: () => <div />,
  TimelineSection: () => <div />,
  RecSection: () => <div />,
  ProjSection: () => <div />,
  OpportunitiesSection: () => <div />,
  AiSection: () => <div />,
  ReportSection: () => <div />,
  FaqSection: () => <div />,
}));

vi.mock('@/components/ui/MaybeShell', () => ({
  MaybeShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ui/DisclosureBundle', () => ({
  DisclosureBundle: () => <div />,
}));

vi.mock('@/components/mf/explore/ExploreSection', () => ({
  SectionHeader: () => <div />,
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------
import PortfolioPage from './page';
import { formatUpdated } from './formatUpdated';
import { useCasUpload } from '@/features/mf/cas-upload';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function renderPage() {
  return render(<PortfolioPage />, { wrapper });
}

type CasPhase = 'idle' | 'uploading' | 'processing' | 'done' | 'error';

function setPhase(phase: CasPhase, extra: Partial<Omit<typeof mockCasUpload, 'phase'>> = {}) {
  const updated = { ...mockCasUpload, phase, ...extra } as typeof mockCasUpload;
  Object.assign(mockCasUpload, updated);
  vi.mocked(useCasUpload).mockReturnValue({ ...mockCasUpload });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  // Reset to idle each test
  Object.assign(mockCasUpload, {
    phase: 'idle',
    progressPct: 0,
    statusLabel: '',
    errorMessage: null,
    errorCode: null,
    estimatedSeconds: null,
    start: vi.fn(),
    reset: vi.fn(),
  });
  vi.mocked(useCasUpload).mockReturnValue({ ...mockCasUpload });
});

// 1. Header toolbar renders the 4 non-upload actions
describe('Header toolbar (dash view)', () => {
  it('renders Refresh, Generate Report, Export buttons', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /Refresh/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /Generate Report/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /Export/i })).toBeDefined();
  });

  it('Auto Sync button is disabled', () => {
    renderPage();
    const autoSync = screen.getByRole('button', { name: /Auto Sync/i });
    expect(autoSync).toBeDefined();
    // disabled attribute present
    expect((autoSync as HTMLButtonElement).disabled).toBe(true);
  });

  it('header toolbar is in page flow (not fixed-positioned)', () => {
    renderPage();
    const toolbar = screen.getByTestId('header-toolbar');
    expect(toolbar).toBeDefined();
    // Not a fixed element — class should not contain "fixed"
    expect(toolbar.className).not.toContain('fixed');
  });
});

// 2. Exactly ONE persistent upload affordance — the FAB
describe('Upload FAB is the sole upload affordance', () => {
  it('renders the FAB with aria-label Upload CAS', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /Upload CAS/i })).toBeDefined();
  });

  it('no old 5-button sticky bar (⬆ Upload Latest CAS not in DOM)', () => {
    renderPage();
    expect(screen.queryByText(/Upload Latest CAS/i)).toBeNull();
  });

  it('FAB is fixed bottom-right', () => {
    renderPage();
    const fab = screen.getByTestId('upload-fab');
    expect(fab.className).toContain('fixed');
    expect(fab.className).toContain('bottom-6');
    expect(fab.className).toContain('right-6');
  });
});

// 3. Clicking the FAB opens the upload popover
describe('FAB click opens popover', () => {
  it('popover not rendered initially', () => {
    renderPage();
    expect(screen.queryByTestId('upload-popover')).toBeNull();
  });

  it('clicking FAB mounts the popover', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('upload-fab'));
    expect(screen.getByTestId('upload-popover')).toBeDefined();
  });

  it('popover contains a file input', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('upload-fab'));
    // sr-only file input inside the popover
    const fileInputs = document.querySelectorAll('input[type="file"]');
    expect(fileInputs.length).toBeGreaterThan(0);
  });

  it('popover contains the password field', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('upload-fab'));
    expect(screen.getByTestId('popover-password-field')).toBeDefined();
    expect(screen.getByLabelText(/PDF password/i)).toBeDefined();
  });
});

// 4. Password reaches casUpload.start
describe('Password flows through to casUpload.start', () => {
  it('calls start with (file, password) when user types password then picks a file', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('upload-fab'));

    // Type password
    const pwdInput = screen.getByLabelText(/PDF password/i);
    fireEvent.change(pwdInput, { target: { value: 'ABCDE1234F' } });

    // Pick file via the hidden input inside the popover
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['dummy'], 'cas.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', { value: [file], configurable: true });
    fireEvent.change(fileInput);

    expect(mockCasUpload.start).toHaveBeenCalledWith(file, 'ABCDE1234F');
  });

  it('calls start with (file, undefined) when password field is empty', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('upload-fab'));

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['dummy'], 'cas.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', { value: [file], configurable: true });
    fireEvent.change(fileInput);

    // password is empty string → start called with undefined
    expect(mockCasUpload.start).toHaveBeenCalledWith(file, undefined);
  });
});

// 5. Popover shows progress when phase=processing
describe('Popover progress state', () => {
  it('shows progress bar and percent when phase=processing', () => {
    setPhase('processing', { progressPct: 55, statusLabel: 'Processing your statement…' });
    renderPage();
    // popover auto-opens when in-flight
    expect(screen.getByTestId('upload-popover')).toBeDefined();
    expect(screen.getByTestId('popover-status')).toBeDefined();
    expect(screen.getByText('55%')).toBeDefined();
    expect(screen.getByText('Processing your statement…')).toBeDefined();
  });
});

// 6. Popover shows error + retry + password when phase=error
describe('Popover error state', () => {
  it('shows error message, Try again, and password field when phase=error', () => {
    setPhase('error', { errorMessage: 'Upload failed — please try again.' });
    renderPage();
    // auto-opens on error
    expect(screen.getByTestId('upload-popover')).toBeDefined();
    expect(screen.getByText(/Upload failed — please try again/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Try again/i })).toBeDefined();
    // password re-shown on error
    expect(screen.getByTestId('popover-password-field')).toBeDefined();
  });
});

// 7 + 8. Escape / X close the popover when idle
describe('Closing the popover', () => {
  it('X button closes the popover', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('upload-fab'));
    expect(screen.getByTestId('upload-popover')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: /Close upload panel/i }));
    expect(screen.queryByTestId('upload-popover')).toBeNull();
  });

  it('Escape closes the popover when idle', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('upload-fab'));
    expect(screen.getByTestId('upload-popover')).toBeDefined();
    act(() => {
      fireEvent.keyDown(document, { key: 'Escape' });
    });
    expect(screen.queryByTestId('upload-popover')).toBeNull();
  });
});

// 9. Breadcrumb "Updated" stamp formatter — dd Mmm, H:00 am/pm (hour-rounded, no year).
describe('formatUpdated', () => {
  it('formats PM, pads the day, and zeroes the minutes', () => {
    // 28 Jun 2026, 21:43 → 9:00 pm (12h conversion + minute rounding)
    expect(formatUpdated(new Date(2026, 5, 28, 21, 43))).toBe('28 Jun, 9:00 pm');
  });

  it('formats midnight as 12:00 am and single-digit days as dd', () => {
    expect(formatUpdated(new Date(2026, 0, 5, 0, 12))).toBe('05 Jan, 12:00 am');
  });

  it('formats noon as 12:00 pm', () => {
    expect(formatUpdated(new Date(2026, 11, 31, 12, 0))).toBe('31 Dec, 12:00 pm');
  });
});

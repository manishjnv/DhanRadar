/**
 * /data-deletion — renders every section heading and the retention table,
 * with the table numbers sourced from dataPolicy.ts (not hardcoded).
 */
import * as React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import DataDeletionPage from './page';
import {
  ERASURE_WAIT_DAYS,
  ERASURE_DUE_DAYS,
  LEGAL_RECORD_YEARS,
  LOG_RETENTION_YEARS,
  FULL_BACKUP_DAYS,
  SUPPORT_EMAIL,
} from '@/lib/dataPolicy';

// MaybeShell is 'use client' and calls useMe() (react-query) — stub it so this
// page renders as a pure unit without a QueryClientProvider.
vi.mock('@/components/ui/MaybeShell', () => ({
  MaybeShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('DataDeletionPage', () => {
  it('renders the h1', () => {
    render(<DataDeletionPage />);
    expect(
      screen.getByRole('heading', { level: 1, name: /Data deletion and retention/i }),
    ).toBeDefined();
  });

  it('renders every section heading', () => {
    render(<DataDeletionPage />);
    [
      'How to delete your account',
      'What happens next',
      'What we delete',
      'What we keep, and why',
      'Backups',
      'Records held by others',
      'Questions',
    ].forEach((heading) => {
      expect(screen.getByRole('heading', { name: heading })).toBeDefined();
    });
  });

  it('renders the retention table with headers and dataPolicy-sourced values', () => {
    render(<DataDeletionPage />);
    expect(screen.getByRole('columnheader', { name: 'Record' })).toBeDefined();
    expect(screen.getByRole('columnheader', { name: 'Why we keep it' })).toBeDefined();
    expect(screen.getByRole('columnheader', { name: 'How long' })).toBeDefined();

    expect(screen.getByRole('rowheader', { name: 'Consent records' })).toBeDefined();
    expect(screen.getAllByText(`${LEGAL_RECORD_YEARS} years`).length).toBeGreaterThan(0);
    expect(screen.getByText(`${LOG_RETENTION_YEARS} year`)).toBeDefined();
  });

  it('mentions the erasure window and backup period from dataPolicy.ts', () => {
    render(<DataDeletionPage />);
    expect(
      screen.getByText(
        new RegExp(`between ${ERASURE_WAIT_DAYS} and ${ERASURE_DUE_DAYS} days`),
      ),
    ).toBeDefined();
    expect(
      screen.getByText(new RegExp(`full backups for ${FULL_BACKUP_DAYS} days`)),
    ).toBeDefined();
  });

  it('links the support email as a mailto link (twice)', () => {
    render(<DataDeletionPage />);
    const links = screen.getAllByRole('link', { name: SUPPORT_EMAIL });
    expect(links.length).toBe(2);
    links.forEach((l) => expect(l.getAttribute('href')).toBe(`mailto:${SUPPORT_EMAIL}`));
  });

  it('shows the last-updated date', () => {
    render(<DataDeletionPage />);
    expect(screen.getByText('Last updated: 30 September 2026')).toBeDefined();
  });
});

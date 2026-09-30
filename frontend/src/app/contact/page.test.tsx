/**
 * /contact — renders the h1, the mailto link, and the data-deletion pointer.
 */
import * as React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import ContactPage from './page';
import { SUPPORT_EMAIL } from '@/lib/dataPolicy';

// MaybeShell is 'use client' and calls useMe() (react-query) — stub it so this
// page renders as a pure unit without a QueryClientProvider.
vi.mock('@/components/ui/MaybeShell', () => ({
  MaybeShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// ContactForm is 'use client' and calls useMe() (react-query) too — it has its
// own dedicated test file with a QueryClientProvider; stub it here so this
// page test stays a pure unit for the static cards below the form.
vi.mock('@/components/contact/ContactForm', () => ({
  ContactForm: () => <div data-testid="contact-form-stub" />,
}));

describe('ContactPage', () => {
  it('renders the h1', () => {
    render(<ContactPage />);
    expect(
      screen.getByRole('heading', { level: 1, name: /Contact us/i }),
    ).toBeDefined();
  });

  it('renders the support email as a mailto link', () => {
    render(<ContactPage />);
    const link = screen.getByRole('link', { name: SUPPORT_EMAIL });
    expect(link.getAttribute('href')).toBe(`mailto:${SUPPORT_EMAIL}`);
  });

  it('links to /data-deletion', () => {
    render(<ContactPage />);
    const link = screen.getByRole('link', { name: 'Data deletion' });
    expect(link.getAttribute('href')).toBe('/data-deletion');
  });
});

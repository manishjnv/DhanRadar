/**
 * AppShell tests — responsive layout + mobile drawer behaviour.
 *
 * next/navigation is mocked minimally: usePathname returns '/dashboard' and
 * useRouter returns a no-op push function (NavLink uses href, not push, but
 * the hook must be defined to avoid "invariant" errors from next internals).
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppShell } from './AppShell';

// ---------------------------------------------------------------------------
// Mock next/navigation — vitest vi.mock hoisted at module level
// ---------------------------------------------------------------------------
vi.mock('next/navigation', () => ({
  usePathname: () => '/dashboard',
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

// ---------------------------------------------------------------------------
// Mock next/link — render as a plain <a> so href/click work in jsdom
// ---------------------------------------------------------------------------
vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    onClick,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    onClick?: React.MouseEventHandler;
    [key: string]: unknown;
  }) => (
    <a href={href} onClick={onClick} {...rest}>
      {children}
    </a>
  ),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function renderShell() {
  // AppShell now calls useMe() (react-query) to decide whether to show the admin
  // nav link, so a QueryClientProvider must wrap it. retry:false keeps the (likely
  // failing/unmocked) /auth/me query from retrying — useMe resolves to no admin,
  // and the nav links under test are always present regardless.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AppShell userSlot={<span data-testid="user-slot">User</span>}>
        <div data-testid="page-content">Page</div>
      </AppShell>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('AppShell', () => {
  it('renders children and userSlot', () => {
    renderShell();
    expect(screen.getByTestId('page-content')).toBeInTheDocument();
    expect(screen.getByTestId('user-slot')).toBeInTheDocument();
  });

  it('renders the desktop aside nav (always in the DOM)', () => {
    renderShell();
    // The desktop <aside> is hidden via CSS (hidden md:flex) but present in DOM.
    // We query via its aria-label on the inner <nav>.
    const navElements = screen.getAllByRole('navigation', { hidden: true });
    // At least one Primary nav should be present (inside aside)
    const primaryNavs = navElements.filter(
      (el) => el.getAttribute('aria-label') === 'Primary',
    );
    expect(primaryNavs.length).toBeGreaterThanOrEqual(1);
  });

  it('has a hamburger button (md:hidden — present in DOM)', () => {
    renderShell();
    const hamburger = screen.getByRole('button', { name: /open navigation/i });
    expect(hamburger).toBeInTheDocument();
  });

  it('drawer dialog is not in DOM before hamburger click', () => {
    renderShell();
    // Drawer is conditionally rendered — not in DOM until opened.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /close navigation/i })).not.toBeInTheDocument();
  });

  it('hamburger click opens the drawer dialog', async () => {
    const user = userEvent.setup();
    renderShell();

    const hamburger = screen.getByRole('button', { name: /open navigation/i });
    await user.click(hamburger);

    // After open, the dialog role=dialog with aria-label="Navigation" is present
    const drawer = screen.getByRole('dialog', { name: /navigation/i });
    expect(drawer).toBeInTheDocument();
  });

  it('Escape closes the drawer', async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole('button', { name: /open navigation/i }));
    // Drawer is open — verify
    expect(screen.getByRole('dialog', { name: /navigation/i })).toBeInTheDocument();

    // Press Escape
    await user.keyboard('{Escape}');

    // Drawer should be closed (dialog still in DOM but not the open dialog)
    expect(screen.queryByRole('dialog', { name: /navigation/i })).not.toBeInTheDocument();
  });

  it('close button closes the drawer', async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole('button', { name: /open navigation/i }));
    const closeBtn = screen.getByRole('button', { name: /close navigation/i });
    await user.click(closeBtn);

    expect(screen.queryByRole('dialog', { name: /navigation/i })).not.toBeInTheDocument();
  });

  it('nav links exist in both desktop aside and mobile drawer', async () => {
    const user = userEvent.setup();
    renderShell();

    // Desktop aside has the "Portfolio" nav link in DOM (CSS hidden md:flex, still in DOM).
    // (The legacy "Upload CAS" side-nav item was decommissioned — upload now lives on /mf/portfolio.)
    const portfolioLinksBeforeOpen = screen.getAllByRole('link', { name: /^portfolio$/i });
    expect(portfolioLinksBeforeOpen.length).toBeGreaterThanOrEqual(1);

    // Open drawer and confirm the "Portfolio" link appears inside the dialog too
    await user.click(screen.getByRole('button', { name: /open navigation/i }));
    const drawer = screen.getByRole('dialog', { name: /navigation/i });
    const portfolioLinkInDrawer = within(drawer).getByRole('link', { name: /^portfolio$/i });
    expect(portfolioLinkInDrawer).toBeInTheDocument();

    // After opening the drawer there are now 2 "Portfolio" links (aside + drawer)
    const portfolioLinksAfterOpen = screen.getAllByRole('link', { name: /^portfolio$/i });
    expect(portfolioLinksAfterOpen.length).toBeGreaterThanOrEqual(2);
  });

  it('backdrop click closes the drawer', async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole('button', { name: /open navigation/i }));
    expect(screen.getByRole('dialog', { name: /navigation/i })).toBeInTheDocument();

    // The backdrop carries an explicit data-testid so this assertion fails
    // loudly if the element is missing (no silent if-guard).
    const backdrop = screen.getByTestId('drawer-backdrop');
    await user.click(backdrop);
    expect(screen.queryByRole('dialog', { name: /navigation/i })).not.toBeInTheDocument();
  });

  it('moves focus into the drawer on open (close button is first focusable)', async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole('button', { name: /open navigation/i }));
    expect(screen.getByRole('button', { name: /close navigation/i })).toHaveFocus();
  });

  it('traps Tab focus inside the open drawer (guard: focus never escapes to the shell)', async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole('button', { name: /open navigation/i }));
    const drawer = screen.getByRole('dialog', { name: /navigation/i });

    // Shift+Tab from the first focusable wraps to the last one INSIDE the drawer
    // (it must not land on the background hamburger / userSlot).
    await user.tab({ shift: true });
    expect(drawer.contains(document.activeElement)).toBe(true);

    // Tabbing forward several times also stays within the drawer.
    for (let i = 0; i < 6; i++) {
      // eslint-disable-next-line no-await-in-loop
      await user.tab();
      expect(drawer.contains(document.activeElement)).toBe(true);
    }
  });

  it('restores focus to the hamburger trigger when the drawer closes', async () => {
    const user = userEvent.setup();
    renderShell();

    const hamburger = screen.getByRole('button', { name: /open navigation/i });
    await user.click(hamburger);
    await user.keyboard('{Escape}');
    expect(hamburger).toHaveFocus();
  });

  it('hamburger aria-expanded reflects the drawer open state', async () => {
    const user = userEvent.setup();
    renderShell();

    const hamburger = screen.getByRole('button', { name: /open navigation/i });
    expect(hamburger).toHaveAttribute('aria-expanded', 'false');

    await user.click(hamburger);
    expect(hamburger).toHaveAttribute('aria-expanded', 'true');

    await user.keyboard('{Escape}');
    expect(hamburger).toHaveAttribute('aria-expanded', 'false');
  });
});

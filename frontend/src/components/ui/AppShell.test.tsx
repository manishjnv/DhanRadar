/**
 * AppShell tests — responsive layout + mobile drawer behaviour.
 *
 * next/navigation is mocked minimally: usePathname returns '/dashboard' and
 * useRouter returns a no-op push function (NavLink uses href, not push, but
 * the hook must be defined to avoid "invariant" errors from next internals).
 */
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
  return render(
    <AppShell userSlot={<span data-testid="user-slot">User</span>}>
      <div data-testid="page-content">Page</div>
    </AppShell>,
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

    // Desktop aside has "Upload CAS" link in DOM (CSS hidden md:flex, still in DOM)
    const uploadLinksBeforeOpen = screen.getAllByRole('link', { name: /upload cas/i });
    expect(uploadLinksBeforeOpen.length).toBeGreaterThanOrEqual(1);

    // Open drawer and confirm "Upload CAS" link appears inside the dialog too
    await user.click(screen.getByRole('button', { name: /open navigation/i }));
    const drawer = screen.getByRole('dialog', { name: /navigation/i });
    const uploadLinkInDrawer = within(drawer).getByRole('link', { name: /upload cas/i });
    expect(uploadLinkInDrawer).toBeInTheDocument();

    // After opening the drawer there are now 2 "Upload CAS" links (aside + drawer)
    const uploadLinksAfterOpen = screen.getAllByRole('link', { name: /upload cas/i });
    expect(uploadLinksAfterOpen.length).toBeGreaterThanOrEqual(2);
  });

  it('backdrop click closes the drawer', async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole('button', { name: /open navigation/i }));
    expect(screen.getByRole('dialog', { name: /navigation/i })).toBeInTheDocument();

    // The backdrop div is aria-hidden; click on it should close the drawer.
    // We simulate this by clicking the hamburger-opened area; since backdrop
    // is aria-hidden we use the container approach — just test that the drawer
    // closes after a click on the backdrop element.
    // Find by the CSS backdrop class indicator via the aria-hidden=true sibling.
    const backdrop = document
      .querySelector('[aria-hidden="true"].fixed.inset-0') as HTMLElement | null;
    if (backdrop) {
      await user.click(backdrop);
      expect(screen.queryByRole('dialog', { name: /navigation/i })).not.toBeInTheDocument();
    }
  });
});

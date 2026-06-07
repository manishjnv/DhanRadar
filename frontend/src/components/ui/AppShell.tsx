'use client';

import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Upload, Compass, Settings, Menu, X, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Nav model — icons come from the lucide line-icon set (consistent stroke /
// size), matching the brand mockup's icon system. No unicode glyphs.
// ---------------------------------------------------------------------------
interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

// Primary workspace destinations (built modules only — future modules like
// Stock/Screener/Watchlist are added here as they ship).
const WORKSPACE: NavItem[] = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/mf/upload', label: 'Upload CAS', icon: Upload },
  { href: '/mood', label: 'Market Mood', icon: Compass },
];

// Settings lives in the footer per the brand-mockup shell.
const SETTINGS: NavItem = { href: '/settings/notifications', label: 'Settings', icon: Settings };

// ---------------------------------------------------------------------------
// NavLink — single source for active state, aria-current, focus ring.
// ---------------------------------------------------------------------------
function NavLink({ item, onClick }: { item: NavItem; onClick?: () => void }) {
  const pathname = usePathname();
  const { href, label, icon: Icon } = item;
  // /settings matches any /settings/* child; others match exact or nested.
  const active = pathname === href || pathname.startsWith(href + '/');
  return (
    <Link
      href={href}
      aria-current={active ? 'page' : undefined}
      onClick={onClick}
      className={cn(
        'flex items-center gap-3 rounded-md px-3 py-2 text-small transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
        active
          ? 'bg-royal/10 text-royal font-medium'
          : 'text-ink-secondary hover:bg-surface-2 hover:text-ink',
      )}
    >
      <Icon size={16} strokeWidth={2} aria-hidden="true" className="shrink-0" />
      {label}
    </Link>
  );
}

// ---------------------------------------------------------------------------
// SidebarContent — shared nav markup used by both the desktop <aside> and the
// mobile drawer, so there is ONE source of nav truth. The optional onNavClick
// callback lets the drawer close itself when a link is activated.
// ---------------------------------------------------------------------------
function SidebarContent({ onNavClick }: { onNavClick?: () => void }) {
  return (
    <>
      {/* Brand lockup — logo mark + wordmark + sub-label (matches brand mockup) */}
      <Link
        href="/dashboard"
        onClick={onNavClick}
        className="flex h-14 items-center gap-2.5 border-b border-line px-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        {/* Decorative mark; the wordmark text provides the accessible name. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/icon.svg" alt="" width={26} height={26} className="shrink-0" />
        <span className="flex flex-col leading-tight">
          <span className="text-body font-medium text-navy">DhanRadar</span>
          <span className="text-caption text-ink-muted">Investor Console</span>
        </span>
      </Link>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-1 p-3" aria-label="Primary">
        <p className="px-3 pb-1 pt-2 text-caption font-medium uppercase tracking-wide text-ink-faint">
          Workspace
        </p>
        {WORKSPACE.map((item) => (
          <NavLink key={item.href} item={item} onClick={onNavClick} />
        ))}
      </nav>

      {/* Footer — Settings + educational note */}
      <div className="flex flex-col gap-2 border-t border-line p-3">
        <NavLink item={SETTINGS} onClick={onNavClick} />
        <p className="px-3 text-caption text-ink-muted">Educational use only</p>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Topbar — `userSlot` is supplied by the (app) layout (the auth UserMenu), so
// this shared shell stays presentation-only and never imports a feature.
// `onMenuOpen` wires the hamburger (mobile only) back to AppShell state.
// ---------------------------------------------------------------------------
function Topbar({
  userSlot,
  onMenuOpen,
  menuOpen = false,
}: {
  userSlot?: React.ReactNode;
  onMenuOpen?: () => void;
  menuOpen?: boolean;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface px-6">
      <div className="flex items-center gap-3">
        {/* Hamburger — only rendered on small screens. aria-expanded reflects
            the actual drawer state (WCAG 4.1.2), driven by AppShell. */}
        <button
          type="button"
          className="md:hidden -ml-2 flex items-center justify-center rounded-md p-2 text-ink-secondary hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
          aria-label="Open navigation"
          aria-expanded={menuOpen}
          onClick={onMenuOpen}
        >
          <Menu size={20} strokeWidth={2} aria-hidden="true" />
        </button>
        <span className="text-small text-ink-muted">Research Analytics</span>
      </div>
      {userSlot}
    </header>
  );
}

// ---------------------------------------------------------------------------
// MobileDrawer — slide-in left drawer for small screens.
// Renders the same SidebarContent as the desktop aside.
// ---------------------------------------------------------------------------
function MobileDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const panelRef = React.useRef<HTMLDivElement>(null);
  const firstFocusRef = React.useRef<HTMLButtonElement>(null);
  // Element focused before the drawer opened, so we can restore it on close.
  const restoreFocusRef = React.useRef<HTMLElement | null>(null);

  // Close on Escape + trap Tab focus inside the drawer (WCAG 2.1.2 / 2.4.3) —
  // a modal drawer must not let keyboard focus wander to the background shell.
  React.useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement as HTMLElement | null;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusables = panel.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      // Wrap at the edges (and re-capture focus if it ever left the panel).
      if (e.shiftKey) {
        if (active === first || !panel.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else if (active === last || !panel.contains(active)) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  // Move focus into the drawer when it opens; restore it to the trigger on close.
  React.useEffect(() => {
    if (open) {
      firstFocusRef.current?.focus();
    } else {
      restoreFocusRef.current?.focus?.();
    }
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 md:hidden"
        aria-hidden="true"
        data-testid="drawer-backdrop"
        onClick={onClose}
      />

      {/* Drawer panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        className="fixed inset-y-0 left-0 z-50 flex w-56 flex-col border-r border-line bg-surface md:hidden"
      >
        {/* Close button at the top-right of the drawer */}
        <button
          ref={firstFocusRef}
          type="button"
          className="absolute right-3 top-3 flex items-center justify-center rounded-md p-1.5 text-ink-secondary hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
          aria-label="Close navigation"
          onClick={onClose}
        >
          <X size={16} strokeWidth={2} aria-hidden="true" />
        </button>

        <SidebarContent onNavClick={onClose} />
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// AppShell
// ---------------------------------------------------------------------------
export interface AppShellProps {
  children: React.ReactNode;
  /** Topbar-right content (identity + logout). Injected by the (app) layout. */
  userSlot?: React.ReactNode;
}

export function AppShell({ children, userSlot }: AppShellProps) {
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const pathname = usePathname();

  // Close the drawer whenever the route changes (user navigated)
  React.useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* Desktop sidebar — hidden on small screens, flex on md+ */}
      <aside className="hidden md:flex h-full w-56 shrink-0 flex-col border-r border-line bg-surface">
        <SidebarContent />
      </aside>

      {/* Mobile drawer + backdrop */}
      <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />

      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar
          userSlot={userSlot}
          menuOpen={drawerOpen}
          onMenuOpen={() => setDrawerOpen(true)}
        />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}

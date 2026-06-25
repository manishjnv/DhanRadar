'use client';

import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, Upload, Compass,
  Settings, Menu, X, BarChart2, ChevronLeft, ChevronRight, Signal,
  ShieldCheck, Search, GitCompare, Trophy, Wallet,
  type LucideIcon,
} from 'lucide-react';
import { CommandPalette } from '@/components/ui/CommandPalette';
import { cn } from '@/lib/cn';
import { SiteFooter } from '@/components/site/SiteFooter';
import { AdminAlertsBell } from '@/components/admin/AdminAlertsBell';
import { useMe } from '@/features/auth/api';
import { PUBLIC_NAV_LINKS } from '@/components/site/SiteHeader';

// ---------------------------------------------------------------------------
// Nav model
// ---------------------------------------------------------------------------
interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const WORKSPACE: NavItem[] = [
  { href: '/dashboard',      label: 'Dashboard',       icon: LayoutDashboard },
  { href: '/mf/upload',      label: 'Upload CAS',      icon: Upload           },
  { href: '/mf/portfolio',   label: 'Portfolio',       icon: Wallet           },
  { href: '/mf/explore',     label: 'Explore Funds',   icon: BarChart2        },
  { href: '/mf/compare',     label: 'Compare Funds',   icon: GitCompare       },
  { href: '/mf/leaderboard', label: 'Leaderboard',     icon: Trophy           },
  { href: '/mood',           label: 'Market Mood',     icon: Compass          },
  { href: '/signal',         label: 'Signal',          icon: Signal           },
  // Tax Guides + Investing Basics intentionally NOT in the sidebar — they live in
  // the footer "Learn" column only (founder 2026-06-22).
];

const SETTINGS: NavItem = { href: '/settings/privacy', label: 'Settings', icon: Settings };
const ADMIN_NAV: NavItem = { href: '/admin', label: 'Admin', icon: ShieldCheck };

// ---------------------------------------------------------------------------
// NavLink
// ---------------------------------------------------------------------------
function NavLink({
  item,
  onClick,
  collapsed = false,
}: {
  item: NavItem;
  onClick?: () => void;
  collapsed?: boolean;
}) {
  const pathname = usePathname();
  const { href, label, icon: Icon } = item;
  const active = pathname === href || pathname.startsWith(href + '/');
  return (
    <Link
      href={href}
      aria-current={active ? 'page' : undefined}
      aria-label={collapsed ? label : undefined}
      title={collapsed ? label : undefined}
      onClick={onClick}
      className={cn(
        'flex items-center rounded-md py-2 text-small transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
        collapsed ? 'justify-center px-2' : 'gap-3 px-3',
        active
          ? 'bg-royal/10 text-royal font-medium'
          : 'text-ink-secondary hover:bg-surface-2 hover:text-ink',
      )}
    >
      <Icon size={16} strokeWidth={2} aria-hidden="true" className="shrink-0" />
      {!collapsed && label}
    </Link>
  );
}

// ---------------------------------------------------------------------------
// SidebarContent — shared by desktop aside + mobile drawer
// ---------------------------------------------------------------------------
function SidebarContent({
  onNavClick,
  collapsed = false,
  onToggle,
  isAdmin = false,
  publicNav = false,
}: {
  onNavClick?: () => void;
  collapsed?: boolean;
  onToggle?: () => void;
  isAdmin?: boolean;
  // When true (mobile drawer on public pages), append the public destinations
  // as a "Browse" group so the top-bar public nav is reachable on small screens
  // from the SAME drawer — no second hamburger.
  publicNav?: boolean;
}) {
  const pathname = usePathname();
  return (
    <>
      {/* Brand lockup */}
      <Link
        href="/dashboard"
        onClick={onNavClick}
        className={cn(
          'flex h-14 items-center border-b border-line focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
          collapsed ? 'justify-center px-2' : 'gap-2.5 px-4',
        )}
        aria-label="DhanRadar — go to dashboard"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/icon.svg" alt="" width={26} height={26} className="shrink-0" />
        {!collapsed && (
          <span className="flex flex-col leading-tight">
            <span className="text-body font-medium text-navy">DhanRadar</span>
            <span className="text-caption text-ink-muted">Investor Console</span>
          </span>
        )}
      </Link>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-1 p-3" aria-label="Primary">
        {!collapsed && (
          <p className="px-3 pb-1 pt-2 text-caption font-medium uppercase tracking-wide text-ink-faint">
            Workspace
          </p>
        )}
        {WORKSPACE.map((item) => (
          <NavLink key={item.href} item={item} onClick={onNavClick} collapsed={collapsed} />
        ))}

        {/* Browse — public destinations, mobile drawer only (publicNav) */}
        {publicNav && !collapsed && (
          <>
            <p className="px-3 pb-1 pt-4 text-caption font-medium uppercase tracking-wide text-ink-faint">
              Browse
            </p>
            {PUBLIC_NAV_LINKS.map((l) => {
              const active =
                pathname === l.href || pathname.startsWith(l.href + '/');
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  onClick={onNavClick}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-small transition-colors',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                    active
                      ? 'bg-royal/10 font-medium text-royal'
                      : 'text-ink-secondary hover:bg-surface-2 hover:text-ink',
                  )}
                >
                  {l.label}
                </Link>
              );
            })}
          </>
        )}
      </nav>

      {/* Footer — settings + collapse toggle */}
      <div className="flex flex-col gap-1 border-t border-line p-3">
        {isAdmin && (
          <NavLink item={ADMIN_NAV} onClick={onNavClick} collapsed={collapsed} />
        )}
        <NavLink item={SETTINGS} onClick={onNavClick} collapsed={collapsed} />

        {/* Collapse toggle — desktop only (onToggle not passed from mobile drawer) */}
        {onToggle && (
          <button
            type="button"
            onClick={onToggle}
            aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            title={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            className={cn(
              'flex items-center rounded-md py-2 text-small transition-colors',
              'text-ink-muted hover:bg-surface-2 hover:text-ink',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
              collapsed ? 'justify-center px-2' : 'gap-3 px-3',
            )}
          >
            {collapsed
              ? <ChevronRight size={16} strokeWidth={2} aria-hidden="true" />
              : <><ChevronLeft size={16} strokeWidth={2} aria-hidden="true" /><span>Collapse</span></>
            }
          </button>
        )}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Topbar
// ---------------------------------------------------------------------------
function Topbar({
  userSlot,
  onMenuOpen,
  onSearchOpen,
  menuOpen = false,
  publicNav = false,
  pathname = '',
}: {
  userSlot?: React.ReactNode;
  onMenuOpen?: () => void;
  onSearchOpen?: () => void;
  menuOpen?: boolean;
  // When true, surface the public destinations inline (desktop) so logged-in
  // users on public pages get the same public nav as the anonymous SiteHeader.
  publicNav?: boolean;
  pathname?: string;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          className="md:hidden -ml-2 flex items-center justify-center rounded-md p-2 text-ink-secondary hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
          aria-label="Open navigation"
          aria-expanded={menuOpen}
          onClick={onMenuOpen}
        >
          <Menu size={20} strokeWidth={2} aria-hidden="true" />
        </button>
        {publicNav ? (
          <nav className="hidden items-center gap-1 lg:flex" aria-label="Browse">
            {PUBLIC_NAV_LINKS.map((l) => {
              const active =
                pathname === l.href || pathname.startsWith(l.href + '/');
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'flex items-center rounded-md px-3 py-2 text-small transition-colors',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                    active
                      ? 'font-medium text-royal'
                      : 'text-ink-secondary hover:text-ink',
                  )}
                >
                  {l.label}
                </Link>
              );
            })}
          </nav>
        ) : (
          <span className="text-small text-ink-muted">Research Analytics</span>
        )}
      </div>
      <div className="flex items-center gap-3">
        {/* Search button — opens the ⌘K command palette */}
        <button
          type="button"
          aria-label="Search funds"
          onClick={onSearchOpen}
          className={cn(
            'flex items-center gap-2 rounded-md px-3 py-1.5',
            'border border-line bg-surface-2 text-small text-ink-secondary',
            'hover:bg-surface-3 hover:text-ink',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
            'transition-colors',
          )}
        >
          <Search size={14} strokeWidth={2} aria-hidden="true" />
          <span className="hidden sm:inline">Search funds</span>
          {/* Keyboard hint chip — hidden on very small screens */}
          <span
            className="hidden rounded border border-line bg-surface px-1 font-mono text-caption text-ink-muted sm:inline"
            aria-hidden="true"
          >
            ⌘K
          </span>
        </button>
        <AdminAlertsBell />
        {userSlot}
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// MobileDrawer — uses same SidebarContent, no collapse in mobile
// ---------------------------------------------------------------------------
function MobileDrawer({ open, onClose, isAdmin, publicNav }: { open: boolean; onClose: () => void; isAdmin?: boolean; publicNav?: boolean }) {
  const panelRef       = React.useRef<HTMLDivElement>(null);
  const firstFocusRef  = React.useRef<HTMLButtonElement>(null);
  const restoreFocusRef = React.useRef<HTMLElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key !== 'Tab') return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusables = panel.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusables.length) return;
      const first = focusables[0];
      const last  = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey) {
        if (active === first || !panel.contains(active)) { e.preventDefault(); last.focus(); }
      } else if (active === last || !panel.contains(active)) {
        e.preventDefault(); first.focus();
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  React.useEffect(() => {
    if (open) firstFocusRef.current?.focus();
    else restoreFocusRef.current?.focus?.();
  }, [open]);

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/40 md:hidden" aria-hidden="true" data-testid="drawer-backdrop" onClick={onClose} />
      <div ref={panelRef} role="dialog" aria-modal="true" aria-label="Navigation" className="fixed inset-y-0 left-0 z-50 flex w-56 flex-col border-r border-line bg-surface md:hidden">
        <button
          ref={firstFocusRef}
          type="button"
          className="absolute right-3 top-3 flex items-center justify-center rounded-md p-1.5 text-ink-secondary hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
          aria-label="Close navigation"
          onClick={onClose}
        >
          <X size={16} strokeWidth={2} aria-hidden="true" />
        </button>
        <SidebarContent onNavClick={onClose} isAdmin={isAdmin} publicNav={publicNav} />
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// AppShell
// ---------------------------------------------------------------------------
export interface AppShellProps {
  children: React.ReactNode;
  userSlot?: React.ReactNode;
  // When true, the top bar surfaces the public destinations (desktop) and the
  // mobile drawer gains a "Browse" group — used on public pages viewed while
  // logged in, so a signed-in user gets the public nav AND the workspace sidebar.
  publicNav?: boolean;
}

export function AppShell({ children, userSlot, publicNav = false }: AppShellProps) {
  const [drawerOpen,  setDrawerOpen]  = React.useState(false);
  const [paletteOpen, setPaletteOpen] = React.useState(false);
  const [collapsed,   setCollapsed]   = React.useState(false);
  const pathname = usePathname();
  const { data: me } = useMe();
  const isAdmin = me?.is_admin === true;

  // Read persisted collapse state after mount (avoids SSR hydration mismatch)
  React.useEffect(() => {
    if (localStorage.getItem('nav-collapsed') === '1') setCollapsed(true);
  }, []);

  const toggleCollapsed = React.useCallback(() => {
    setCollapsed((v) => {
      const next = !v;
      localStorage.setItem('nav-collapsed', next ? '1' : '0');
      return next;
    });
  }, []);

  React.useEffect(() => { setDrawerOpen(false); }, [pathname]);

  // Global ⌘K / Ctrl+K shortcut — opens the command palette
  React.useEffect(() => {
    function handleGlobalKey(e: KeyboardEvent) {
      const isModifier = e.metaKey || e.ctrlKey;
      if (isModifier && e.key === 'k') {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      }
    }
    document.addEventListener('keydown', handleGlobalKey);
    return () => document.removeEventListener('keydown', handleGlobalKey);
  }, []);

  return (
    <div className="flex h-[calc(100dvh_-_var(--dev-banner-h,0px))] overflow-hidden bg-bg">
      {/* Desktop sidebar — animates between w-56 (expanded) and w-14 (collapsed) */}
      <aside
        className={cn(
          'hidden md:flex h-full shrink-0 flex-col border-r border-line bg-surface',
          'transition-[width] duration-200 ease-in-out overflow-hidden',
          collapsed ? 'w-14' : 'w-56',
        )}
      >
        <SidebarContent collapsed={collapsed} onToggle={toggleCollapsed} isAdmin={isAdmin} />
      </aside>

      {/* Mobile drawer */}
      <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} isAdmin={isAdmin} publicNav={publicNav} />

      {/* ⌘K Command palette */}
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />

      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar
          userSlot={userSlot}
          menuOpen={drawerOpen}
          onMenuOpen={() => setDrawerOpen(true)}
          onSearchOpen={() => setPaletteOpen(true)}
          publicNav={publicNav}
          pathname={pathname}
        />
        <main className="flex-1 overflow-y-auto p-6">
          <div className="flex min-h-full flex-col">
            <div className="flex-1">{children}</div>
            {/* The shared global SiteFooter — universal for ALL users (anonymous get it
                via MaybeShell; logged-in get the SAME footer here). Full-bleed: the
                negative margins cancel the <main> p-6 so it sits flush at the bottom.
                SiteFooter carries the standing SEBI Disclaimer. */}
            <div className="-mx-6 -mb-6 mt-8">
              <SiteFooter />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

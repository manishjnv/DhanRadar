'use client';

import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Upload, Compass, Settings, type LucideIcon } from 'lucide-react';
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
function NavLink({ item }: { item: NavItem }) {
  const pathname = usePathname();
  const { href, label, icon: Icon } = item;
  // /settings matches any /settings/* child; others match exact or nested.
  const active = pathname === href || pathname.startsWith(href + '/');
  return (
    <Link
      href={href}
      aria-current={active ? 'page' : undefined}
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
// Sidebar
// ---------------------------------------------------------------------------
function Sidebar() {
  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-line bg-surface">
      {/* Brand lockup — logo mark + wordmark + sub-label (matches brand mockup) */}
      <Link
        href="/dashboard"
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
          <NavLink key={item.href} item={item} />
        ))}
      </nav>

      {/* Footer — Settings + educational note */}
      <div className="flex flex-col gap-2 border-t border-line p-3">
        <NavLink item={SETTINGS} />
        <p className="px-3 text-caption text-ink-muted">Educational use only</p>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Topbar — `userSlot` is supplied by the (app) layout (the auth UserMenu), so
// this shared shell stays presentation-only and never imports a feature.
// ---------------------------------------------------------------------------
function Topbar({ userSlot }: { userSlot?: React.ReactNode }) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface px-6">
      <span className="text-small text-ink-muted">Research Analytics</span>
      {userSlot}
    </header>
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
  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar userSlot={userSlot} />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}

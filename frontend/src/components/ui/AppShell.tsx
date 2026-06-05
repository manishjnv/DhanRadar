'use client';

import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Nav items
// ---------------------------------------------------------------------------
const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: '⊞' },
  { href: '/mf/upload', label: 'Upload CAS', icon: '↑' },
];

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------
function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-line bg-surface">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2 border-b border-line px-4">
        <span className="text-h3 font-medium text-navy">DhanRadar</span>
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-1 p-3" aria-label="Main navigation">
        {NAV_ITEMS.map(({ href, label, icon }) => {
          const active = pathname === href || pathname.startsWith(href + '/');
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-small transition-colors',
                active
                  ? 'bg-royal/10 text-royal font-medium'
                  : 'text-ink-secondary hover:bg-surface-2 hover:text-ink',
              )}
            >
              <span aria-hidden="true" className="w-4 text-center">{icon}</span>
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-line p-4">
        <p className="text-caption text-ink-muted">Educational use only</p>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Topbar
// ---------------------------------------------------------------------------
function Topbar() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface px-6">
      <span className="text-small text-ink-muted">Research Analytics</span>
      {/* Mock user avatar */}
      <div className="flex items-center gap-2">
        <span className="text-small text-ink-secondary">Manish K.</span>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-royal/10 text-caption font-medium text-royal">
          MK
        </div>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// AppShell
// ---------------------------------------------------------------------------
export interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}

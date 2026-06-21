'use client';

/**
 * AdminShell — operator-only shell for /admin/* and /admin/ai/* routes.
 *
 * variant="admin"  → red accent  (#E5484D  → token: red)
 * variant="aiops"  → amber accent (#EA580C  → closest token: amber #F5A623,
 *                    but spec says #EA580C; we use Tailwind arbitrary value
 *                    scoped to the shell since no amber-aiops token exists)
 *
 * Sidebar: always visible ≥lg; icon-only collapse at md; hidden on mobile.
 * No bottom tab bar (desktop-first per Admin.md §9).
 * Shell-switching link in footer ("↔ AI Ops" / "↔ Admin").
 */

import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Activity,
  Users,
  CreditCard,
  BarChart3,
  Flag,
  HeadphonesIcon,
  TrendingUp,
  Bell,
  Bot,
  GitBranch,
  FileText,
  CheckCircle2,
  ShieldAlert,
  ThumbsUp,
  DollarSign,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Nav model
// ---------------------------------------------------------------------------
interface AdminNavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  live?: boolean; // false = visible but inert (disabled) in Phase 1
}

const ADMIN_NAV: AdminNavItem[] = [
  { href: '/admin',            label: 'Overview',          icon: LayoutDashboard, live: true  },
  { href: '/admin/operations', label: 'Data Operations',   icon: Activity,        live: true  },
  { href: '/admin/users',      label: 'Users',             icon: Users,           live: true  },
  { href: '/admin/billing',    label: 'Billing',           icon: CreditCard,      live: true  },
  { href: '/admin/scoring',    label: 'Scoring',           icon: BarChart3,       live: true  },
  { href: '/admin/flags',      label: 'Feature Flags',     icon: Flag,            live: true  },
  { href: '/admin/support',    label: 'Support',           icon: HeadphonesIcon,  live: true  },
  { href: '/admin/analytics',  label: 'Analytics',         icon: TrendingUp,      live: true  },
  { href: '/admin/notifications', label: 'Notifications',  icon: Bell,            live: true  },
];

const AIOPS_NAV: AdminNavItem[] = [
  { href: '/admin/ai',           label: 'AI Overview',            icon: Bot,          live: true },
  { href: '/admin/ai/versions',  label: 'Score History',          icon: GitBranch,    live: true },
  { href: '/admin/ai/prompts',   label: 'AI Prompts',             icon: FileText,     live: true },
  { href: '/admin/ai/eval',      label: 'Data Quality',           icon: CheckCircle2, live: true },
  { href: '/admin/ai/safety',    label: 'Recommendation Safety',  icon: ShieldAlert,  live: true },
  { href: '/admin/ai/feedback',  label: 'User Feedback',          icon: ThumbsUp,     live: true },
  { href: '/admin/ai/cost',      label: 'AI Usage & Cost',        icon: DollarSign,   live: true },
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
export type AdminShellVariant = 'admin' | 'aiops';

export interface AdminShellProps {
  children: React.ReactNode;
  variant?: AdminShellVariant;
}

// ---------------------------------------------------------------------------
// Accent helpers
// ---------------------------------------------------------------------------
function accentClasses(variant: AdminShellVariant) {
  if (variant === 'aiops') {
    return {
      activeItem:    'bg-amber/10 text-amber font-medium',
      topBorder:     'border-t-[3px] border-t-amber',
      badgeText:     'text-amber',
      badgeBg:       'bg-amber/10',
      roleBadge:     'bg-amber/10 text-amber',
      contextText:   'Internal · ML ops',
      roleLabelText: 'AI Ops',
    };
  }
  return {
    activeItem:    'bg-red/10 text-red font-medium',
    topBorder:     'border-t-[3px] border-t-red',
    badgeText:     'text-red',
    badgeBg:       'bg-red/10',
    roleBadge:     'bg-red/10 text-red',
    contextText:   'Internal · audited session',
    roleLabelText: 'Admin',
  };
}

// ---------------------------------------------------------------------------
// NavItem
// ---------------------------------------------------------------------------
function NavItem({
  item,
  active,
  variant,
}: {
  item: AdminNavItem;
  active: boolean;
  variant: AdminShellVariant;
}) {
  const accent = accentClasses(variant);
  const Icon = item.icon;

  if (!item.live) {
    return (
      <span
        className={cn(
          'flex items-center gap-2.5 rounded-md px-3 py-2 text-small',
          'text-ink-faint cursor-not-allowed opacity-50',
        )}
        aria-disabled="true"
        title={`${item.label} (coming soon)`}
      >
        <Icon size={15} strokeWidth={2} aria-hidden="true" className="shrink-0" />
        {item.label}
      </span>
    );
  }

  return (
    <Link
      href={item.href}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'flex items-center gap-2.5 rounded-md px-3 py-2 text-small transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
        active
          ? accent.activeItem
          : 'text-ink-secondary hover:bg-surface-2 hover:text-ink',
      )}
    >
      <Icon size={15} strokeWidth={2} aria-hidden="true" className="shrink-0" />
      {item.label}
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------
function AdminSidebar({ variant }: { variant: AdminShellVariant }) {
  const pathname = usePathname();
  const accent = accentClasses(variant);
  const nav = variant === 'aiops' ? AIOPS_NAV : ADMIN_NAV;
  const switchHref  = variant === 'aiops' ? '/admin' : '/admin/ai';
  const switchLabel = variant === 'aiops' ? '↔ Admin shell' : '↔ AI Ops shell';

  return (
    <aside className="hidden md:flex h-full w-56 shrink-0 flex-col border-r border-line bg-surface">
      {/* Brand + accent stripe */}
      <Link
        href="/"
        aria-label="DhanRadar home"
        className={cn(
          'flex h-14 items-center gap-2.5 border-b border-line px-4',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
          accent.topBorder,
        )}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/icon.svg" alt="" width={24} height={24} className="shrink-0" />
        <span className="flex flex-col leading-tight">
          <span className="text-body font-medium text-navy">DhanRadar</span>
          <span className={cn('text-caption font-medium', accent.badgeText)}>
            {accent.roleLabelText}
          </span>
        </span>
      </Link>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-0.5 p-3 overflow-y-auto" aria-label={`${accent.roleLabelText} navigation`}>
        <p className="px-3 pb-1 pt-2 text-caption font-medium uppercase tracking-wide text-ink-faint">
          {variant === 'aiops' ? 'AI Operations' : 'Operations'}
        </p>
        {nav.map((item) => {
          // Exact match for /admin and /admin/ai to avoid all routes matching
          const active =
            item.href === '/admin' || item.href === '/admin/ai'
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(item.href + '/');
          return (
            <NavItem key={item.href} item={item} active={active} variant={variant} />
          );
        })}
      </nav>

      {/* Footer — shell switch */}
      <div className="border-t border-line p-3">
        <Link
          href={switchHref}
          className="flex items-center gap-2 rounded-md px-3 py-2 text-small text-ink-secondary hover:bg-surface-2 hover:text-ink transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
        >
          <Bot size={14} strokeWidth={2} aria-hidden="true" />
          {switchLabel}
        </Link>
        <Link
          href="/dashboard"
          className="flex items-center gap-2 rounded-md px-3 py-2 text-small text-ink-secondary hover:bg-surface-2 hover:text-ink transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
        >
          ← Back to app
        </Link>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Topbar
// ---------------------------------------------------------------------------
function AdminTopbar({ variant }: { variant: AdminShellVariant }) {
  const accent = accentClasses(variant);
  return (
    <header className={cn(
      'flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface px-6',
      accent.topBorder,
    )}>
      <div className="flex items-center gap-3">
        <span className="text-small text-ink-muted">{accent.contextText}</span>
      </div>
      <span className={cn('rounded-md px-2.5 py-1 text-caption font-medium', accent.roleBadge)}>
        role: {accent.roleLabelText}
      </span>
    </header>
  );
}

// ---------------------------------------------------------------------------
// AdminShell
// ---------------------------------------------------------------------------
export function AdminShell({ children, variant = 'admin' }: AdminShellProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <AdminSidebar variant={variant} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <AdminTopbar variant={variant} />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}

'use client';

/**
 * Admin route-group layout.
 *
 * Guard: fetches /api/v1/auth/me via the shared useMe() hook.
 * If is_admin !== true → renders Next.js notFound() (404 — surface-hiding,
 * not a "403 access denied" screen, per Admin.md §2).
 *
 * Note: this is a CLIENT component guard (UX gate). The real security boundary
 * is RequireAdmin() on every backend endpoint (HTTP 404 to non-admins).
 *
 * Note on ECONNREFUSED: this layout is a Client Component so it will never
 * execute a server-side backend fetch at build time. The `export const dynamic`
 * guard below ensures Next.js does not try to statically render admin pages.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { notFound } from 'next/navigation';
import { AdminShell } from '@/components/admin/AdminShell';
import { useMe } from '@/features/auth/api';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { data: user, isLoading } = useMe();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <div
          className="h-6 w-6 animate-spin rounded-full border-2 border-line border-t-red"
          role="status"
          aria-label="Checking admin access"
        />
      </div>
    );
  }

  if (!user || !user.is_admin) {
    // Surface-hiding: 404, not 403.
    notFound();
    return null;
  }

  return <AdminShell variant="admin">{children}</AdminShell>;
}

import { redirect } from 'next/navigation';

export const dynamic = 'force-dynamic';

/**
 * /admin → redirect to /admin/overview (canonical overview URL).
 * The layout guard has already verified is_admin before this runs.
 */
export default function AdminRootPage() {
  redirect('/admin/overview');
}

import Link from 'next/link';
import { Disclaimer } from '@/components/ui/Disclaimer';

/**
 * Auth layout — centered card shell for /login and /signup. Deliberately does
 * NOT use AppShell (no sidebar/topbar): these pages are pre-session.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-bg px-4 py-10">
      <div className="w-full max-w-sm">
        <Link href="/" className="mb-8 flex flex-col items-center gap-1 text-center">
          <span className="text-h2 font-medium text-navy">DhanRadar</span>
          <span className="text-small text-ink-muted">
            Educational market intelligence
          </span>
        </Link>

        {children}

        <Disclaimer className="mt-6 text-center" />
      </div>
    </main>
  );
}

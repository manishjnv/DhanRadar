import Link from 'next/link';
import { Disclaimer } from '@/components/ui/Disclaimer';

/**
 * Auth layout — desktop: warm split panel (navy brand left, form right).
 * Mobile: stacked single-column (brand lockup above form).
 * a11y: brand panel is aria-hidden (decorative); form column is <main>.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-bg md:flex">
      {/* Left brand panel — desktop only, decorative */}
      <div
        aria-hidden="true"
        className="hidden md:flex md:w-5/12 flex-col justify-between bg-navy px-10 py-12"
      >
        <div>
          <p className="text-h2 font-medium text-white">DhanRadar</p>
          <p className="mt-1 text-small text-white/60">
            Educational market intelligence
          </p>
        </div>
        <div className="space-y-3">
          <p className="text-h3 font-medium text-white leading-snug">
            Understand your mutual fund portfolio in 60 seconds.
          </p>
          <p className="text-small text-white/60">
            Upload your CAS statement for an educational label analysis of your
            holdings — no buy, sell, or hold recommendations, ever.
          </p>
        </div>
        <p className="text-caption text-white/40">Not investment advice.</p>
      </div>

      {/* Right: auth form */}
      <main className="flex flex-1 flex-col items-center justify-center px-4 py-10">
        {/* Brand lockup — mobile only */}
        <Link
          href="/"
          className="mb-8 flex flex-col items-center gap-1 text-center md:hidden"
        >
          <span className="text-h2 font-medium text-navy">DhanRadar</span>
          <span className="text-small text-ink-muted">
            Educational market intelligence
          </span>
        </Link>

        <div className="w-full max-w-sm">
          {children}
        </div>

        <Disclaimer className="mt-6 text-center" />
      </main>
    </div>
  );
}

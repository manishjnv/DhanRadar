import Image from 'next/image';
import Link from 'next/link';
import { Disclaimer } from '@/components/ui/Disclaimer';

/**
 * Auth layout — B5 branded treatment.
 *
 * Desktop: navy brand panel (left ~42%) + form panel (right).
 * Mobile: single column — logo lockup above form card.
 *
 * a11y: brand panel is aria-hidden (decorative). Form column is <main>.
 * Tokens: all values from live Geist/warm token set. No ad-hoc colours.
 */

const VALUE_PROPS = [
  'Educational labels for every fund — never buy/sell advice',
  'Upload your CAS for a 60-second portfolio analysis',
  'AI research grounded in your own holdings',
];

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-bg md:flex">

      {/* ── Brand panel (desktop only, decorative) ─────────────────────── */}
      <div
        aria-hidden="true"
        className="hidden md:flex md:w-5/12 lg:w-[42%] flex-col justify-between bg-navy px-10 py-12 relative overflow-hidden"
      >
        {/* Faint radar backdrop — bottom-right */}
        <svg
          aria-hidden="true"
          className="pointer-events-none select-none absolute -bottom-10 -right-10 opacity-[0.07]"
          width="340" height="340" viewBox="0 0 340 340" fill="none"
        >
          <circle cx="170" cy="170" r="160" stroke="white" strokeWidth="1" />
          <circle cx="170" cy="170" r="110" stroke="white" strokeWidth="1" />
          <circle cx="170" cy="170" r="60"  stroke="white" strokeWidth="1" />
          <circle cx="170" cy="170" r="15"  stroke="white" strokeWidth="1" />
          <line x1="170" y1="170" x2="305" y2="98" stroke="white" strokeWidth="1" />
          <circle cx="280" cy="111" r="5" fill="#1FD79A" opacity="0.9" />
        </svg>

        {/* Logo */}
        <div>
          <Image
            src="/brand/logo-mono-dark.svg"
            alt="DhanRadar"
            width={200}
            height={50}
            priority
            className="h-10 w-auto"
          />
          <p className="mt-2 text-[11px] tracking-widest uppercase text-white/50">
            Educational market intelligence
          </p>
        </div>

        {/* Headline + value props */}
        <div className="space-y-5">
          <h2 className="font-serif text-[26px] leading-[1.28] font-normal text-white">
            Understand your mutual fund portfolio in&nbsp;60&nbsp;seconds.
          </h2>
          <ul className="space-y-3">
            {VALUE_PROPS.map((item) => (
              <li key={item} className="flex items-start gap-2.5">
                <svg
                  aria-hidden="true"
                  className="mt-[3px] shrink-0 h-4 w-4 text-emerald-dark"
                  viewBox="0 0 16 16" fill="none"
                >
                  <path
                    d="M3 8l3.5 3.5L13 4.5"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <span className="text-small text-white/70 leading-snug">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Footer disclaimer */}
        <p className="text-caption text-white/35">
          For education only. Not investment advice.
        </p>
      </div>

      {/* ── Form panel ─────────────────────────────────────────────────── */}
      <main className="flex flex-1 flex-col items-center justify-center px-4 py-10 animate-fade-up">

        {/* Mobile brand lockup (hidden md+) */}
        <Link
          href="/"
          className="mb-8 flex flex-col items-center gap-1.5 md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded-xl p-2 -m-2"
          aria-label="DhanRadar — home"
        >
          <Image
            src="/brand/logo-primary.svg"
            alt="DhanRadar"
            width={180}
            height={45}
            priority
            className="block dark:hidden h-9 w-auto"
          />
          <Image
            src="/brand/logo-mono-dark.svg"
            alt="DhanRadar"
            width={180}
            height={45}
            priority
            className="hidden dark:block h-9 w-auto"
          />
          <span className="text-[11px] tracking-widest uppercase text-ink-muted">
            Educational market intelligence
          </span>
        </Link>

        {/* Auth card */}
        <div className="w-full max-w-sm">
          {children}
        </div>

        <Disclaimer className="mt-6 text-center max-w-xs" />
      </main>
    </div>
  );
}

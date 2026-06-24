/**
 * Root layout — DhanRadar
 *
 * Brand fonts are self-hosted via next/font (no layout shift, no extra request,
 * no Google round-trip for Geist): Geist Sans + Geist Mono from the official
 * `geist` package, Instrument Serif (editorial accent) from next/font/google.
 * Each exposes a CSS variable (--font-geist-sans / --font-geist-mono /
 * --font-instrument-serif) that the token pipeline references as the FIRST
 * family in tokens.json → tokens.css (--dr-font-*) + the Tailwind preset.
 *
 * DO NOT switch to Manrope or Inter — Geist + warm palette is the canonical
 * brand identity (tokens.json, architecture non-negotiable #8).
 */
import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import { Instrument_Serif } from 'next/font/google';
import { Providers } from './providers';
import { DevBanner } from '@/components/site/DevBanner';
import './globals.css';
import '@/styles/tokens.css';

const instrumentSerif = Instrument_Serif({
  subsets: ['latin'],
  weight: '400',
  style: ['normal', 'italic'],
  variable: '--font-instrument-serif',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'DhanRadar',
  description: 'AI-powered Indian mutual fund & stock radar',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // Font variables scoped on <html> so --dr-font-* resolve to the self-hosted
    // brand faces everywhere; `font-sans` applies Geist Sans by default.
    <html
      lang="en"
      // overflow-x-clip: guard against document-level horizontal scroll on
      // mobile. Nested scroll-snap carousels (e.g. Fund Detail "Similar Funds")
      // leak phantom horizontal overflow to the viewport on real mobile Chrome,
      // letting the whole page drag sideways (made obvious by the fixed dev
      // banner clipping on the left). `clip` (not `hidden`) stops it without
      // creating a scroll container — sticky headers and internal
      // overflow-x-auto carousels/tables keep working.
      className={`${GeistSans.variable} ${GeistMono.variable} ${instrumentSerif.variable} overflow-x-clip`}
    >
      <body className="font-sans bg-bg text-ink antialiased overflow-x-clip">
        <Providers>
          {/* Global pre-release notice — fixed bar; publishes its height as
              --dev-banner-h so the wrapper below reserves space, SiteHeader
              offsets its sticky top, and AppShell shrinks its viewport height. */}
          <DevBanner />
          <div style={{ paddingTop: 'var(--dev-banner-h, 0px)' }}>{children}</div>
        </Providers>
      </body>
    </html>
  );
}

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
      className={`${GeistSans.variable} ${GeistMono.variable} ${instrumentSerif.variable}`}
    >
      <body className="font-sans bg-bg text-ink antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

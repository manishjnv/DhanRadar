/**
 * Root layout — DhanRadar
 *
 * Font: Geist via CSS font-family (tokens.css sets --dr-font-sans).
 * If Geist font files are not bundled, the fallback chain resolves to
 * ui-sans-serif / system-ui automatically.
 *
 * @font-face placeholder — uncomment and provide woff2 paths when font
 * files are available under public/fonts/:
 *
 *   @font-face {
 *     font-family: 'Geist';
 *     src: url('/fonts/Geist-Regular.woff2') format('woff2');
 *     font-weight: 100 900;
 *     font-display: swap;
 *   }
 *
 * DO NOT switch to Manrope or Inter — Geist + warm palette is the
 * canonical brand font (tokens.json, architecture non-negotiable #8).
 */
import type { Metadata } from 'next';
import { Providers } from './providers';
import '@/styles/tokens.css';

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
    <html lang="en">
      {/* font-sans resolves Geist → ui-sans-serif via tailwind.tokens.cjs */}
      <body className="font-sans bg-bg text-ink antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

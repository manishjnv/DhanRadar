import Link from 'next/link';
import { Button } from '@/components/ui/Button';
import { Disclaimer } from '@/components/ui/Disclaimer';

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-bg px-4 text-center">
      <h1 className="text-h1 font-medium text-navy">DhanRadar</h1>
      <p className="mt-4 max-w-md text-body text-ink-secondary">
        Upload your mutual fund Consolidated Account Statement and get an
        educational, label-based portfolio report in about 60 seconds.
      </p>

      <div className="mt-8 flex flex-col gap-3 sm:flex-row">
        <Button asChild size="lg">
          <Link href="/signup">Get started — it&apos;s free</Link>
        </Button>
        <Button asChild size="lg" variant="outline">
          <Link href="/login">Log in</Link>
        </Button>
      </div>

      <Link
        href="/learn/tax"
        className="mt-6 rounded text-small text-ink-secondary underline underline-offset-2 transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        Or explore our free Tax Education guides →
      </Link>

      <Disclaimer className="mt-10 max-w-md" />
    </main>
  );
}

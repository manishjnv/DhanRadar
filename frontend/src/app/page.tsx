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
      <p className="mt-2 text-small text-ink-muted">
        Educational research only — never investment advice.
      </p>

      <div className="mt-8 flex flex-col gap-3 sm:flex-row">
        <Button asChild size="lg">
          <Link href="/signup">Get started — it&apos;s free</Link>
        </Button>
        <Button asChild size="lg" variant="outline">
          <Link href="/login">Log in</Link>
        </Button>
      </div>

      <Disclaimer className="mt-10 max-w-md" />
    </main>
  );
}

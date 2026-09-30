/**
 * /contact — Public compliance page: how to reach us.
 *
 * Server Component (no 'use client'); public, no login required — same
 * posture as /data-deletion. Chrome (SiteHeader/SiteFooter or AppShell) comes
 * from MaybeShell. No backend fetch (avoids SSR build-time ECONNREFUSED).
 *
 * SUPPORT_EMAIL comes from frontend/src/lib/dataPolicy.ts — never hardcode.
 *
 * Compliance: plain factual copy only, no advisory verbs, no numeric fund
 * score. Not a score/label/AI surface, so no <DisclosureBundle/> is needed —
 * the standing <Disclaimer/> from SiteFooter/AppShell chrome is sufficient.
 */
import type { Metadata } from 'next';
import Link from 'next/link';
import { Card, CardBody } from '@/components/ui/Card';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { SUPPORT_EMAIL } from '@/lib/dataPolicy';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Contact us · DhanRadar',
  description: 'How to reach DhanRadar — write to us at connect@dhanradar.com.',
};

export default function ContactPage() {
  return (
    <MaybeShell>
      <div className="mb-8">
        <p className="text-caption text-ink-muted uppercase tracking-wide mb-1">
          Support
        </p>
        <h1 className="text-h2 text-ink">Contact us</h1>
        <p className="text-small text-ink-secondary mt-2">
          We read every email. Here is how to reach us and what to send.
        </p>
      </div>

      <div className="space-y-6">
        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">Write to us</h2>
            <p className="text-small text-ink-secondary leading-relaxed">
              Send us an email at{' '}
              <a
                href={`mailto:${SUPPORT_EMAIL}`}
                className="text-royal underline underline-offset-2"
              >
                {SUPPORT_EMAIL}
              </a>
              . Use the email address you signed up with, so we can find your
              account.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">
              What not to send
            </h2>
            <p className="text-small text-ink-secondary leading-relaxed">
              Never send your password, one-time code (OTP), full PAN, or bank
              details over email. We will never ask for these.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">
              Deleting your account
            </h2>
            <p className="text-small text-ink-secondary leading-relaxed">
              To delete your account, see{' '}
              <Link
                href="/data-deletion"
                className="text-royal underline underline-offset-2"
              >
                Data deletion
              </Link>
              .
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">
              What DhanRadar is
            </h2>
            <p className="text-small text-ink-secondary leading-relaxed">
              DhanRadar is an educational platform for understanding mutual
              funds. We don&apos;t give investment advice.
            </p>
          </CardBody>
        </Card>
      </div>
    </MaybeShell>
  );
}

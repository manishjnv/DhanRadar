/**
 * /data-deletion — Public compliance page: data deletion + retention.
 *
 * Server Component (no 'use client'); public, no login required — same
 * posture as /methodology. Chrome (SiteHeader/SiteFooter or AppShell) comes
 * from MaybeShell. No backend fetch (avoids SSR build-time ECONNREFUSED).
 *
 * All periods below come from frontend/src/lib/dataPolicy.ts, which mirrors
 * backend/dhanradar/compliance/data_policy.py — never hardcode a number here.
 *
 * Compliance: plain factual copy only, no advisory verbs, no numeric fund
 * score. Not a score/label/AI surface, so no <DisclosureBundle/> is needed —
 * the standing <Disclaimer/> from SiteFooter/AppShell chrome is sufficient.
 */
import type { Metadata } from 'next';
import Link from 'next/link';
import { Card, CardBody } from '@/components/ui/Card';
import { MaybeShell } from '@/components/ui/MaybeShell';
import {
  ERASURE_WAIT_DAYS,
  ERASURE_DUE_DAYS,
  LEGAL_RECORD_YEARS,
  LOG_RETENTION_YEARS,
  FULL_BACKUP_DAYS,
  SUPPORT_EMAIL,
} from '@/lib/dataPolicy';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Data deletion and retention · DhanRadar',
  description:
    'How to delete your DhanRadar account, what happens next, what we delete, what we keep and why, and how long.',
};

const RETENTION_ROWS: { record: string; why: string; howLong: string }[] = [
  {
    record: 'Consent records',
    why: 'to show you agreed to our terms and data use',
    howLong: `${LEGAL_RECORD_YEARS} years`,
  },
  {
    record: 'Records of AI summaries shown to you',
    why: 'regulatory audit trail',
    howLong: `${LEGAL_RECORD_YEARS} years`,
  },
  {
    record: 'Payment records',
    why: 'tax and accounting laws',
    howLong: `${LEGAL_RECORD_YEARS} years`,
  },
  {
    record: 'Security and admin logs',
    why: "India's data protection rules require them",
    howLong: `${LOG_RETENTION_YEARS} year`,
  },
];

function RetentionTable() {
  return (
    <table className="w-full max-[480px]:block">
      <thead className="max-[480px]:hidden">
        <tr className="border-b border-line">
          <th scope="col" className="px-3 py-2 text-left text-small font-semibold text-ink">
            Record
          </th>
          <th scope="col" className="px-3 py-2 text-left text-small font-semibold text-ink">
            Why we keep it
          </th>
          <th scope="col" className="px-3 py-2 text-left text-small font-semibold text-ink">
            How long
          </th>
        </tr>
      </thead>
      <tbody className="max-[480px]:block">
        {RETENTION_ROWS.map((row) => (
          <tr
            key={row.record}
            className="border-b border-line max-[480px]:block max-[480px]:rounded-md max-[480px]:border max-[480px]:mb-3 max-[480px]:p-3 max-[480px]:last:mb-0"
          >
            <th
              scope="row"
              className="px-3 py-2 text-left text-small font-medium text-ink max-[480px]:block max-[480px]:px-0 max-[480px]:pt-0"
            >
              {row.record}
            </th>
            <td
              data-label="Why we keep it"
              className="px-3 py-2 text-small text-ink-secondary max-[480px]:flex max-[480px]:justify-between max-[480px]:gap-3 max-[480px]:px-0 max-[480px]:before:content-[attr(data-label)] max-[480px]:before:font-semibold max-[480px]:before:text-ink-muted"
            >
              {row.why}
            </td>
            <td
              data-label="How long"
              className="px-3 py-2 text-small text-ink-secondary max-[480px]:flex max-[480px]:justify-between max-[480px]:gap-3 max-[480px]:px-0 max-[480px]:before:content-[attr(data-label)] max-[480px]:before:font-semibold max-[480px]:before:text-ink-muted"
            >
              {row.howLong}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function DataDeletionPage() {
  return (
    <MaybeShell>
      <div className="mb-8">
        <p className="text-caption text-ink-muted uppercase tracking-wide mb-1">
          Privacy
        </p>
        <h1 className="text-h2 text-ink">Data deletion and retention</h1>
        <p className="text-small text-ink-secondary mt-2">
          How to delete your account, what happens next, and what we keep.
        </p>
      </div>

      <div className="space-y-6">
        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">
              How to delete your account
            </h2>
            <p className="text-small text-ink-secondary leading-relaxed">
              Go to Settings → Privacy → &quot;Delete my account&quot;. If you
              can&apos;t sign in, write to{' '}
              <a
                href={`mailto:${SUPPORT_EMAIL}`}
                className="text-royal underline underline-offset-2"
              >
                {SUPPORT_EMAIL}
              </a>{' '}
              from your registered email.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">
              What happens next
            </h2>
            <ul className="space-y-2">
              {[
                'We email you right away to confirm the request.',
                'You are signed out.',
                `Your account is deleted between ${ERASURE_WAIT_DAYS} and ${ERASURE_DUE_DAYS} days after the request.`,
                `Until day ${ERASURE_WAIT_DAYS}, you can keep your account using the link in the email.`,
                'We email you again once it is done.',
              ].map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <span
                    className="mt-1.5 h-1.5 w-1.5 rounded-full bg-royal shrink-0"
                    aria-hidden="true"
                  />
                  <p className="text-small text-ink-secondary leading-relaxed">{item}</p>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">What we delete</h2>
            <p className="text-small text-ink-secondary leading-relaxed mb-3">
              Your profile and sign-in details, portfolios, holdings and
              transactions, watchlist and alerts, notifications, feedback you
              gave on AI summaries, and all sign-in sessions.
            </p>
            <p className="text-small text-ink-secondary leading-relaxed">
              Statements (CAS files) you upload are not kept: we delete the
              file right after reading it.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">
              What we keep, and why
            </h2>
            <div className="overflow-hidden rounded-md border border-line">
              <RetentionTable />
            </div>
            <p className="text-small text-ink-muted mt-4 leading-relaxed">
              These records carry only a random ID — not your name, email,
              phone or PAN. They are deleted automatically when the period
              ends.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">Backups</h2>
            <p className="text-small text-ink-secondary leading-relaxed">
              We keep full backups for {FULL_BACKUP_DAYS} days to recover
              from failures. If we ever restore one, deleted accounts are
              deleted again.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">
              Records held by others
            </h2>
            <p className="text-small text-ink-secondary leading-relaxed">
              If you invested through DhanRadar, BSE, the fund houses and
              their registrars keep your KYC and order records, and Razorpay
              keeps payment records, under their own legal duties. Contact
              them for those records.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">Questions</h2>
            <p className="text-small text-ink-secondary leading-relaxed">
              Write to{' '}
              <a
                href={`mailto:${SUPPORT_EMAIL}`}
                className="text-royal underline underline-offset-2"
              >
                {SUPPORT_EMAIL}
              </a>
              .
            </p>
          </CardBody>
        </Card>

        <p className="text-caption text-ink-muted">
          Last updated: 30 September 2026
        </p>
      </div>
    </MaybeShell>
  );
}

'use client';

/**
 * Cancel-deletion — the "keep my account" link emailed on a deletion request.
 *
 * NEVER auto-submits on load: email scanners / preview bots open links, and an
 * auto-POST would let a scanner accidentally cancel (or, worse, be mistaken for
 * a real cancel by the user reading the page before clicking). The user must
 * press the button.
 *
 * States: no token (invalid, no button) · idle (button enabled) · submitting
 * (spinner, disabled) · success (confirmation + Sign in) · 400 (not valid/expired,
 * points to SUPPORT_EMAIL) · network error (retry).
 */

import * as React from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/apiClient';
import { useCancelAccountDeletion } from '@/features/auth/api';
import { SUPPORT_EMAIL } from '@/lib/dataPolicy';

type ViewState = 'no_token' | 'idle' | 'submitting' | 'success' | 'invalid' | 'network_error';

function CancelDeletionForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get('token');
  const { mutate, isPending } = useCancelAccountDeletion();

  const [state, setState] = React.useState<ViewState>(token ? 'idle' : 'no_token');

  function submit() {
    if (!token) return;
    setState('submitting');
    mutate(token, {
      onSuccess: () => setState('success'),
      onError: (err) => {
        if (err instanceof ApiError && err.problem.status === 400) {
          setState('invalid');
        } else {
          setState('network_error');
        }
      },
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Keep your DhanRadar account?</CardTitle>
      </CardHeader>
      <CardBody className="flex flex-col gap-4">
        {state === 'no_token' && (
          <p role="alert" className="text-small text-ink-secondary leading-relaxed">
            This link is missing its confirmation code. Open the link from your deletion
            email again, or write to{' '}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="text-royal underline underline-offset-2">
              {SUPPORT_EMAIL}
            </a>
            .
          </p>
        )}

        {(state === 'idle' || state === 'submitting') && (
          <>
            <p className="text-small text-ink-secondary leading-relaxed">
              If you asked us to delete your account, clicking below cancels that request.
              You can keep using DhanRadar as normal.
            </p>
            <div>
              <Button type="button" onClick={submit} disabled={isPending}>
                {isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                Keep my account
              </Button>
            </div>
          </>
        )}

        {state === 'success' && (
          <div role="status" className="flex flex-col gap-4">
            <p className="text-small text-ink leading-relaxed">
              Your account is safe. You can sign in again.
            </p>
            <div>
              <Button type="button" onClick={() => router.push('/login')}>
                Sign in
              </Button>
            </div>
          </div>
        )}

        {state === 'invalid' && (
          <p role="alert" className="text-small text-ink-secondary leading-relaxed">
            This link is not valid or has expired. If your account is not deleted yet,
            write to{' '}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="text-royal underline underline-offset-2">
              {SUPPORT_EMAIL}
            </a>
            .
          </p>
        )}

        {state === 'network_error' && (
          <div role="alert" className="flex flex-col gap-4">
            <p className="text-small text-ink-secondary leading-relaxed">
              We couldn&apos;t reach DhanRadar. Check your connection and try again.
            </p>
            <div>
              <Button type="button" variant="outline" onClick={submit}>
                Retry
              </Button>
            </div>
          </div>
        )}

        <p className="text-caption text-ink-muted">
          <Link href="/" className="text-royal underline underline-offset-2">
            Back to DhanRadar
          </Link>
        </p>
      </CardBody>
    </Card>
  );
}

export default function CancelDeletionPage() {
  return (
    <React.Suspense fallback={null}>
      <CancelDeletionForm />
    </React.Suspense>
  );
}

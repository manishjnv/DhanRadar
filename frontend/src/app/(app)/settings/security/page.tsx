'use client';

/**
 * Security settings — TOTP authenticator app management.
 *
 * State machine:
 *  - totp_verified = true  → confirmation state (no disable flow yet; backend
 *                            has none — do not invent one).
 *  - totp_verified = false → setup flow:
 *      1. "Set up authenticator app" → POST /auth/totp/setup → shows
 *         provisioning_uri (as selectable otpauth:// text) + base32 secret
 *         with a copy button. No QR dep added; see report for decision note.
 *      2. 6-digit code input (auto-focus) + Verify button → POST /auth/totp/verify.
 *      3. On success: me cache invalidated → totp_verified flips → confirmation state.
 *
 * Layout and components mirror the privacy page exactly.
 */

import * as React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardBody,
} from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, Field } from '@/components/ui/Input';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { ApiError } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import { useMe, useTotpSetup, useTotpVerify } from '@/features/auth/api';

// ---------------------------------------------------------------------------
// CopyButton — copies text to clipboard and shows a brief confirmation.
// ---------------------------------------------------------------------------
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = React.useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Could not copy to clipboard.');
    }
  }

  return (
    <Button type="button" variant="outline" size="sm" onClick={handleCopy}>
      {copied ? 'Copied!' : 'Copy'}
    </Button>
  );
}

// ---------------------------------------------------------------------------
// SetupFlow — drives the TOTP enrollment UX (setup → verify → done).
// ---------------------------------------------------------------------------
function SetupFlow() {
  const qc = useQueryClient();
  const setup = useTotpSetup();
  const verify = useTotpVerify();
  const [code, setCode] = React.useState('');
  const [verifyError, setVerifyError] = React.useState<string | null>(null);
  const codeRef = React.useRef<HTMLInputElement>(null);

  // Auto-focus the code input once setup data arrives.
  React.useEffect(() => {
    if (setup.data) {
      codeRef.current?.focus();
    }
  }, [setup.data]);

  function handleSetup() {
    setup.mutate(undefined, {
      onError: () => toast.error('Could not initiate TOTP setup. Please try again.'),
    });
  }

  function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setVerifyError(null);
    verify.mutate(
      { code },
      {
        onSuccess: () => {
          // Invalidate the me query so totp_verified flips to true.
          qc.invalidateQueries({ queryKey: queryKeys.auth.me() });
          toast.success('Authenticator app enabled.');
        },
        onError: (err) => {
          if (err instanceof ApiError) {
            const { status, detail } = err.problem;
            if (status === 400 && detail === 'totp_invalid') {
              setVerifyError('Invalid code. Check your authenticator app and try again.');
            } else if (status === 429) {
              setVerifyError('Too many attempts. Please wait a minute and try again.');
            } else {
              setVerifyError('Something went wrong. Please try again.');
            }
          } else {
            setVerifyError('Something went wrong. Please try again.');
          }
          setCode('');
          codeRef.current?.focus();
        },
      },
    );
  }

  // Step 1: initiate setup
  if (!setup.data) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-body text-ink-secondary">
          Set up an authenticator app (Google Authenticator, Authy, 1Password, etc.)
          to sign in with a one-time code instead of your password.
        </p>
        <Button
          type="button"
          variant="primary"
          size="md"
          disabled={setup.isPending}
          onClick={handleSetup}
          className="self-start"
        >
          {setup.isPending ? 'Generating…' : 'Set up authenticator app'}
        </Button>
      </div>
    );
  }

  // Step 2: show provisioning info + code input
  const { provisioning_uri, secret } = setup.data;

  return (
    <form onSubmit={handleVerify} className="flex flex-col gap-5">
      {/* QR placeholder — no QR lib installed; show the raw URI + secret for
          manual entry. A future dependency decision (e.g. `qrcode.react`) is
          needed to render a scannable image; flagged in the implementation report. */}
      <div className="flex flex-col gap-2">
        <p className="text-small font-medium text-ink">
          1. Scan or enter this key in your authenticator app
        </p>
        <p className="text-caption text-ink-muted">
          If your app supports scanning a QR code, copy the URI below and use your
          app&apos;s &ldquo;Add account manually&rdquo; option, or ask your app to open
          the otpauth:// link. A scannable QR image will be added once a QR library
          is approved for this project.
        </p>
        <div className="flex items-center gap-2 rounded-md border border-line bg-surface-2 px-3 py-2">
          <code
            className="flex-1 break-all font-mono text-caption text-ink select-all"
            aria-label="Provisioning URI — select all and copy"
          >
            {provisioning_uri}
          </code>
          <CopyButton text={provisioning_uri} />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-small font-medium text-ink">
          Manual entry — base32 secret
        </p>
        <div className="flex items-center gap-2 rounded-md border border-line bg-surface-2 px-3 py-2">
          <code
            className="flex-1 break-all font-mono text-caption text-ink select-all tabular-nums tracking-widest"
            aria-label="Base32 TOTP secret"
          >
            {secret}
          </code>
          <CopyButton text={secret} />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <p className="text-small font-medium text-ink">
          2. Enter the 6-digit code shown by your app to verify
        </p>
        <Field id="totp-code" label="Verification code" error={verifyError ?? undefined}>
          <Input
            id="totp-code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            pattern="\d{6}"
            placeholder="000000"
            ref={codeRef}
            value={code}
            onChange={(e) => {
              setVerifyError(null);
              setCode(e.target.value.replace(/\D/g, '').slice(0, 6));
            }}
            aria-invalid={!!verifyError}
            className="tracking-widest max-w-[12rem]"
          />
        </Field>

        {verifyError && (
          <p className="text-small text-red" role="alert">
            {verifyError}
          </p>
        )}

        <Button
          type="submit"
          variant="primary"
          size="md"
          disabled={code.length < 6 || verify.isPending}
          className="self-start"
        >
          {verify.isPending ? 'Verifying…' : 'Verify and enable'}
        </Button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// SecurityPage
// ---------------------------------------------------------------------------
export default function SecurityPage() {
  const { data: user, isLoading, isError, refetch } = useMe();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 max-w-2xl">
        <div className="flex flex-col gap-1">
          <Skeleton className="h-7 w-40 rounded-md" />
          <Skeleton className="h-4 w-72 rounded-md" />
        </div>
        <Card>
          <CardBody className="flex flex-col gap-4">
            <Skeleton className="h-10 w-full rounded-md" />
            <Skeleton className="h-10 w-48 rounded-md" />
          </CardBody>
        </Card>
      </div>
    );
  }

  if (isError || !user) {
    return (
      <ErrorCard
        title="Could not load your security settings"
        message="Check your connection and try again."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      {/* Page heading */}
      <div className="flex flex-col gap-1">
        <h1 className="text-h2 text-ink">Security</h1>
        <p className="text-small text-ink-secondary">
          Manage how you sign in to your DhanRadar account.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Authenticator app (TOTP)</CardTitle>
          <CardDescription>
            Set up an authenticator app to sign in with a 6-digit one-time code
            instead of your password — an alternative way to log in, not a second
            factor.
          </CardDescription>
        </CardHeader>
        <CardBody>
          {user.totp_verified ? (
            <div className="flex flex-col gap-2">
              <p className="text-body text-ink">
                Authenticator app is enabled — you can sign in with a 6-digit code.
              </p>
              <p className="text-caption text-ink-muted">
                To disable authenticator sign-in, please contact support.
              </p>
            </div>
          ) : (
            <SetupFlow />
          )}
        </CardBody>
      </Card>
    </div>
  );
}

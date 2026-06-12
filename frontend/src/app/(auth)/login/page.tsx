'use client';

/**
 * Login — email + password (default) OR TOTP one-time code.
 *
 * Modes:
 *  - password  (default): email + password → POST /auth/login
 *  - totp:               email + 6-digit code → POST /auth/totp/login
 *                        auto-submits when the 6th digit lands and email is valid.
 *
 * Google SSO: full-page redirect to GET /api/v1/auth/google/start?next=…
 * Error params: ?error=google_auth_failed | account_deletion_pending are read on mount.
 */

import * as React from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, Field } from '@/components/ui/Input';
import { ApiError } from '@/lib/apiClient';
import { useLogin, useTotpLogin } from '@/features/auth/api';
import type { Credentials } from '@/features/auth/types';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Derive the API base the same way apiClient does: NEXT_PUBLIC_API_URL (if set)
// stripped of trailing slash; otherwise same-origin /api/v1.
const API_BASE =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL
    : '/api/v1'
  ).replace(/\/$/, '');

// `next` is read from the query string, so this inner component must live under
// a <Suspense> boundary (Next 14 app-router requirement for useSearchParams).
function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { mutate: login, isPending: loginPending } = useLogin();
  const { mutate: totpLogin, isPending: totpPending } = useTotpLogin();

  const [mode, setMode] = React.useState<'password' | 'totp'>('password');
  const [formError, setFormError] = React.useState<string | null>(null);
  // code is managed in local state (not react-hook-form) so auto-submit
  // can fire synchronously from the onChange handler.
  const [codeValue, setCodeValue] = React.useState('');
  const [codeError, setCodeError] = React.useState<string | null>(null);

  // Prevents double-fire of auto-submit in the same keystroke.
  const autoSubmitFiredRef = React.useRef(false);
  const codeInputRef = React.useRef<HTMLInputElement>(null);

  const isPending = loginPending || totpPending;

  const {
    register,
    handleSubmit,
    getValues,
    trigger,
    formState: { errors },
  } = useForm<Credentials>({ mode: 'onSubmit' });

  function safeNext(): string {
    const next = params.get('next');
    // Only allow same-origin relative paths — never absolute/external URLs.
    // Backslashes are folded into '/' by browsers ('/\evil.com' leaves the
    // origin), so reject them outright.
    if (
      next &&
      next.startsWith('/') &&
      !next.startsWith('//') &&
      !next.includes('\\')
    ) {
      return next;
    }
    return '/dashboard';
  }

  // Read URL error params on mount.
  React.useEffect(() => {
    const errorParam = params.get('error');
    if (errorParam === 'google_auth_failed') {
      setFormError('Google sign-in failed. Please try again.');
    } else if (errorParam === 'account_deletion_pending') {
      setFormError('This account has a pending deletion request.');
    } else if (errorParam === 'account_exists_use_password') {
      setFormError(
        'An account with this email already exists — log in with your password.',
      );
    }
    // params is stable for the lifetime of the page — this runs once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Focus the code input whenever TOTP mode is activated.
  React.useEffect(() => {
    if (mode === 'totp') {
      codeInputRef.current?.focus();
    }
  }, [mode]);

  function handleGoogleSSO() {
    window.location.assign(
      `${API_BASE}/auth/google/start?next=${encodeURIComponent(safeNext())}`,
    );
  }

  function switchToTotp() {
    setFormError(null);
    setCodeError(null);
    setCodeValue('');
    autoSubmitFiredRef.current = false;
    setMode('totp');
  }

  function switchToPassword() {
    setFormError(null);
    setCodeError(null);
    setCodeValue('');
    autoSubmitFiredRef.current = false;
    setMode('password');
  }

  function handleLoginError(err: unknown) {
    if (err instanceof ApiError) {
      const { status, detail } = err.problem;
      if (status === 401) {
        setFormError('Invalid email or password.');
      } else if (status === 403 && detail === 'account_deletion_pending') {
        setFormError('This account has a pending deletion request.');
      } else if (status === 429) {
        setFormError('Too many attempts. Please wait a minute and try again.');
      } else {
        setFormError('Something went wrong. Please try again.');
      }
    } else {
      setFormError('Something went wrong. Please try again.');
    }
  }

  function handleTotpError(err: unknown) {
    if (err instanceof ApiError) {
      const { status, detail } = err.problem;
      if (status === 401) {
        setFormError('Invalid code. Please try again.');
        setCodeValue('');
        codeInputRef.current?.focus();
      } else if (status === 403 && detail === 'account_deletion_pending') {
        setFormError('This account has a pending deletion request.');
      } else if (status === 429) {
        setFormError('Too many attempts. Please wait a minute and try again.');
      } else {
        setFormError('Something went wrong. Please try again.');
      }
    } else {
      setFormError('Something went wrong. Please try again.');
    }
    autoSubmitFiredRef.current = false;
  }

  function onPasswordSubmit(values: Credentials) {
    setFormError(null);
    login(values, {
      onSuccess: () => router.replace(safeNext()),
      onError: handleLoginError,
    });
  }

  function submitTotpCredentials(email: string, code: string) {
    if (isPending) return;
    setFormError(null);
    totpLogin(
      { email, code },
      {
        onSuccess: () => router.replace(safeNext()),
        onError: handleTotpError,
      },
    );
  }

  function onTotpManualSubmit(values: Credentials) {
    // Manual submit from the "Log in" button — uses the current codeValue.
    if (!codeValue || codeValue.length < 6) {
      setCodeError('Enter your 6-digit authenticator code.');
      return;
    }
    setCodeError(null);
    autoSubmitFiredRef.current = false;
    submitTotpCredentials(values.email, codeValue);
  }

  async function handleCodeChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 6);
    setCodeValue(raw);
    setCodeError(null);

    if (raw.length === 6) {
      // Validate the email field first.
      const emailValid = await trigger('email');
      if (!emailValid) {
        // Show email error and focus the email field.
        const emailInput = document.getElementById('email') as HTMLInputElement | null;
        emailInput?.focus();
        return;
      }

      if (autoSubmitFiredRef.current || isPending) return;
      autoSubmitFiredRef.current = true;
      submitTotpCredentials(getValues('email'), raw);
    } else {
      autoSubmitFiredRef.current = false;
    }
  }

  // react-hook-form handleSubmit routes to the right handler based on mode.
  function onSubmit(values: Credentials) {
    if (mode === 'password') {
      onPasswordSubmit(values);
    } else {
      onTotpManualSubmit(values);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Log in</CardTitle>
      </CardHeader>
      <CardBody>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
          {/* Email — shared across both modes */}
          <Field id="email" label="Email" error={errors.email?.message}>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              aria-invalid={!!errors.email}
              placeholder="you@example.com"
              {...register('email', {
                required: 'Email is required.',
                pattern: { value: EMAIL_RE, message: 'Enter a valid email address.' },
              })}
            />
          </Field>

          {mode === 'password' ? (
            <Field id="password" label="Password" error={errors.password?.message}>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={!!errors.password}
                {...register('password', { required: 'Password is required.' })}
              />
            </Field>
          ) : (
            <Field id="code" label="Authenticator code" error={codeError ?? undefined}>
              <Input
                id="code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                pattern="\d{6}"
                placeholder="000000"
                autoFocus
                ref={codeInputRef}
                value={codeValue}
                onChange={handleCodeChange}
                aria-invalid={!!codeError}
                className="tracking-widest"
              />
            </Field>
          )}

          {formError && (
            <p className="text-small text-red" role="alert">
              {formError}
            </p>
          )}

          <Button type="submit" size="lg" disabled={isPending} className="w-full">
            {isPending ? 'Logging in…' : 'Log in'}
          </Button>

          {/* Mode switcher */}
          {mode === 'password' ? (
            <button
              type="button"
              onClick={switchToTotp}
              className="text-small text-ink-secondary hover:text-ink text-center"
            >
              Sign in with an authenticator code instead
            </button>
          ) : (
            <button
              type="button"
              onClick={switchToPassword}
              className="text-small text-ink-secondary hover:text-ink text-center"
            >
              Use password instead
            </button>
          )}
        </form>

        {/* Divider */}
        <div className="relative my-4">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-line" />
          </div>
          <div className="relative flex justify-center">
            <span className="bg-surface px-2 text-caption text-ink-muted">or</span>
          </div>
        </div>

        {/* Google SSO */}
        <Button
          type="button"
          variant="secondary"
          size="lg"
          className="w-full"
          onClick={handleGoogleSSO}
        >
          Continue with Google
        </Button>

        <p className="mt-4 text-center text-small text-ink-secondary">
          New to DhanRadar?{' '}
          <Link href="/signup" className="font-medium text-royal hover:underline">
            Create an account
          </Link>
        </p>
      </CardBody>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <React.Suspense fallback={null}>
      <LoginForm />
    </React.Suspense>
  );
}

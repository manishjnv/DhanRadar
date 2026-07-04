'use client';

/**
 * Login — email + password (default) OR email OTP (one-time code sent to inbox).
 *
 * Modes:
 *  - password    (default): email + password → POST /auth/login
 *  - email_otp:             email → POST /auth/email-otp/request → 6-digit code
 *                           → POST /auth/email-otp/login
 *                           auto-submits when the 6th digit lands and email is valid.
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
import { useLogin, useRequestEmailOtp, useEmailOtpLogin } from '@/features/auth/api';
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
  const { mutate: requestOtp, isPending: requestPending } = useRequestEmailOtp();
  const { mutate: emailOtpLogin, isPending: emailOtpLoginPending } = useEmailOtpLogin();

  const [mode, setMode] = React.useState<'password' | 'email_otp'>('password');
  // email_otp phase: 'request' = pre-send, 'code' = code input shown
  const [otpPhase, setOtpPhase] = React.useState<'request' | 'code'>('request');
  const [formError, setFormError] = React.useState<string | null>(null);
  // code is managed in local state (not react-hook-form) so auto-submit
  // can fire synchronously from the onChange handler.
  const [codeValue, setCodeValue] = React.useState('');
  const [codeError, setCodeError] = React.useState<string | null>(null);

  // Resend countdown: null = not started; 0 = enabled; >0 = seconds remaining.
  const [resendCountdown, setResendCountdown] = React.useState<number | null>(null);
  const resendIntervalRef = React.useRef<ReturnType<typeof setInterval> | null>(null);

  // Prevents double-fire of auto-submit in the same keystroke.
  const autoSubmitFiredRef = React.useRef(false);
  const codeInputRef = React.useRef<HTMLInputElement>(null);

  const isPending = loginPending || requestPending || emailOtpLoginPending;

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
    return '/mf/portfolio';
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

  // Focus the code input whenever email_otp code phase is activated.
  React.useEffect(() => {
    if (mode === 'email_otp' && otpPhase === 'code') {
      codeInputRef.current?.focus();
    }
  }, [mode, otpPhase]);

  // Clear interval on unmount.
  React.useEffect(() => {
    return () => {
      if (resendIntervalRef.current) clearInterval(resendIntervalRef.current);
    };
  }, []);

  function startResendCountdown() {
    if (resendIntervalRef.current) clearInterval(resendIntervalRef.current);
    setResendCountdown(60);
    resendIntervalRef.current = setInterval(() => {
      setResendCountdown((prev) => {
        if (prev === null || prev <= 1) {
          if (resendIntervalRef.current) clearInterval(resendIntervalRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }

  function handleGoogleSSO() {
    window.location.assign(
      `${API_BASE}/auth/google/start?next=${encodeURIComponent(safeNext())}`,
    );
  }

  function switchToEmailOtp() {
    setFormError(null);
    setCodeError(null);
    setCodeValue('');
    setOtpPhase('request');
    setResendCountdown(null);
    if (resendIntervalRef.current) clearInterval(resendIntervalRef.current);
    autoSubmitFiredRef.current = false;
    setMode('email_otp');
  }

  function switchToPassword() {
    setFormError(null);
    setCodeError(null);
    setCodeValue('');
    setOtpPhase('request');
    setResendCountdown(null);
    if (resendIntervalRef.current) clearInterval(resendIntervalRef.current);
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

  function handleEmailOtpLoginError(err: unknown) {
    if (err instanceof ApiError) {
      const { status, detail } = err.problem;
      if (status === 401) {
        setCodeError('Invalid or expired code. Please try again.');
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

  async function handleRequestOtp() {
    // Validate email before firing the request.
    const emailValid = await trigger('email');
    if (!emailValid) {
      const emailInput = document.getElementById('email') as HTMLInputElement | null;
      emailInput?.focus();
      return;
    }
    setFormError(null);
    const email = getValues('email');
    requestOtp(
      { email },
      {
        onSuccess: () => {
          setOtpPhase('code');
          startResendCountdown();
        },
        onError: (err) => {
          if (err instanceof ApiError && err.problem.status === 503) {
            setFormError('Email code login is not available right now.');
          } else if (err instanceof ApiError && err.problem.status === 429) {
            setFormError('Too many requests. Please wait a minute.');
          } else {
            setFormError('Something went wrong. Please try again.');
          }
        },
      },
    );
  }

  async function handleResend() {
    setFormError(null);
    const email = getValues('email');
    requestOtp(
      { email },
      {
        onSuccess: () => {
          startResendCountdown();
        },
        onError: (err) => {
          if (err instanceof ApiError && err.problem.status === 429) {
            setFormError('Too many requests. Please wait a minute.');
          } else {
            setFormError('Something went wrong. Please try again.');
          }
        },
      },
    );
  }

  function submitEmailOtpCredentials(email: string, code: string) {
    if (isPending) return;
    setCodeError(null);
    emailOtpLogin(
      { email, code },
      {
        onSuccess: () => router.replace(safeNext()),
        onError: handleEmailOtpLoginError,
      },
    );
  }

  async function handleCodeChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 6);
    setCodeValue(raw);
    setCodeError(null);

    if (raw.length === 6) {
      // Validate the email field first.
      const emailValid = await trigger('email');
      if (!emailValid) {
        const emailInput = document.getElementById('email') as HTMLInputElement | null;
        emailInput?.focus();
        return;
      }

      if (autoSubmitFiredRef.current || isPending) return;
      autoSubmitFiredRef.current = true;
      submitEmailOtpCredentials(getValues('email'), raw);
    } else {
      autoSubmitFiredRef.current = false;
    }
  }

  function onPasswordSubmit(values: Credentials) {
    setFormError(null);
    login(values, {
      onSuccess: () => router.replace(safeNext()),
      onError: handleLoginError,
    });
  }

  // react-hook-form handleSubmit routes to the right handler based on mode.
  function onSubmit(values: Credentials) {
    if (mode === 'password') {
      onPasswordSubmit(values);
    } else if (mode === 'email_otp') {
      if (otpPhase === 'request') {
        // Enter pressed in the email field during request phase.
        handleRequestOtp();
      } else {
        // Manual submit from the "Log in" button (or Enter key) in code phase.
        if (codeValue.length === 6) {
          autoSubmitFiredRef.current = false;
          submitEmailOtpCredentials(values.email, codeValue);
        } else {
          setCodeError('Enter the 6-digit code from your email.');
        }
      }
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
            /* email_otp mode */
            <>
              {otpPhase === 'code' && (
                <>
                  <p className="text-small text-ink-secondary">
                    We sent a 6-digit code to your email. It expires in 10 minutes.
                  </p>
                  <Field id="code" label="Email code" error={codeError ?? undefined}>
                    <Input
                      id="code"
                      type="text"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={6}
                      pattern="\d{6}"
                      placeholder="000000"
                      ref={codeInputRef}
                      value={codeValue}
                      onChange={handleCodeChange}
                      aria-invalid={!!codeError}
                      className="tracking-widest"
                    />
                  </Field>
                </>
              )}
            </>
          )}

          {formError && (
            <p className="text-small text-red" role="alert">
              {formError}
            </p>
          )}

          {mode === 'password' ? (
            <Button type="submit" size="lg" disabled={isPending} className="w-full">
              {isPending ? 'Logging in…' : 'Log in'}
            </Button>
          ) : (
            /* email_otp: phase-specific action buttons, no form submit */
            otpPhase === 'request' ? (
              <Button
                type="button"
                size="lg"
                disabled={isPending}
                className="w-full"
                onClick={handleRequestOtp}
              >
                {isPending ? 'Sending…' : 'Email me a login code'}
              </Button>
            ) : (
              /* phase 'code': primary submit + resend button (countdown-gated) */
              <>
                <Button type="submit" size="lg" disabled={isPending} className="w-full">
                  {isPending ? 'Logging in…' : 'Log in'}
                </Button>
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={isPending || (resendCountdown !== null && resendCountdown > 0)}
                  className="text-small text-ink-secondary hover:text-ink text-center disabled:opacity-40"
                >
                  {resendCountdown !== null && resendCountdown > 0
                    ? `Resend code (${resendCountdown}s)`
                    : 'Resend code'}
                </button>
              </>
            )
          )}

          {/* Mode switcher */}
          {mode === 'password' ? (
            <Button
              type="button"
              variant="secondary"
              size="lg"
              className="w-full"
              onClick={switchToEmailOtp}
            >
              Sign in with email code
            </Button>
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

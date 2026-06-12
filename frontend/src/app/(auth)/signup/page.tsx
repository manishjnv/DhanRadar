'use client';

/**
 * Signup — create a free-tier account (POST /auth/signup). Password min length
 * (10) mirrors the backend SignupRequest bound. Duplicate email returns 409.
 *
 * Google SSO also auto-creates accounts on first sign-in via
 * GET /api/v1/auth/google/start?next=…
 *
 * After signup the user has no risk_profile yet; once the Onboarding screen
 * (and its backend write endpoint) lands, route new accounts to /onboarding.
 * Until then they go to the dashboard cold-start state.
 */

import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, Field } from '@/components/ui/Input';
import { ApiError } from '@/lib/apiClient';
import { useSignup } from '@/features/auth/api';
import type { Credentials } from '@/features/auth/types';

const API_BASE =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL
    : '/api/v1'
  ).replace(/\/$/, '');

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function SignupPage() {
  const router = useRouter();
  const { mutate: signup, isPending } = useSignup();
  const [formError, setFormError] = React.useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Credentials>({ mode: 'onSubmit' });

  function onSubmit(values: Credentials) {
    setFormError(null);
    signup(values, {
      // TODO(onboarding): route to /onboarding once the risk-profile screen
      // and its backend write endpoint exist.
      onSuccess: () => router.replace('/dashboard'),
      onError: (err) => {
        if (err instanceof ApiError && err.problem.status === 409) {
          setFormError('An account with this email already exists. Try logging in.');
        } else if (err instanceof ApiError && err.problem.status === 429) {
          setFormError('Too many attempts. Please wait a minute and try again.');
        } else {
          setFormError('Something went wrong. Please try again.');
        }
      },
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create your account</CardTitle>
      </CardHeader>
      <CardBody>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
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

          <Field
            id="password"
            label="Password"
            hint="At least 10 characters."
            error={errors.password?.message}
          >
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              aria-invalid={!!errors.password}
              {...register('password', {
                required: 'Password is required.',
                minLength: { value: 10, message: 'Password must be at least 10 characters.' },
                maxLength: { value: 128, message: 'Password is too long.' },
              })}
            />
          </Field>

          {formError && (
            <p className="text-small text-red" role="alert">
              {formError}
            </p>
          )}

          <Button type="submit" size="lg" disabled={isPending} className="w-full">
            {isPending ? 'Creating account…' : 'Create account'}
          </Button>
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

        {/* Google SSO — auto-creates account on first sign-in */}
        <Button
          type="button"
          variant="secondary"
          size="lg"
          className="w-full"
          onClick={() =>
            window.location.assign(
              `${API_BASE}/auth/google/start?next=${encodeURIComponent('/dashboard')}`,
            )
          }
        >
          Continue with Google
        </Button>

        <p className="mt-4 text-center text-small text-ink-secondary">
          Already have an account?{' '}
          <Link href="/login" className="font-medium text-royal hover:underline">
            Log in
          </Link>
        </p>
      </CardBody>
    </Card>
  );
}

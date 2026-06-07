'use client';

/**
 * Login — email + password against POST /auth/login (cookie session).
 * The 401 is intentionally generic ("invalid_credentials") server-side, so we
 * never disclose whether the email exists.
 */

import * as React from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, Field } from '@/components/ui/Input';
import { ApiError } from '@/lib/apiClient';
import { useLogin } from '@/features/auth/api';
import type { Credentials } from '@/features/auth/types';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// `next` is read from the query string, so this inner component must live under
// a <Suspense> boundary (Next 14 app-router requirement for useSearchParams).
function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { mutate: login, isPending } = useLogin();
  const [formError, setFormError] = React.useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Credentials>({ mode: 'onSubmit' });

  function safeNext(): string {
    const next = params.get('next');
    // Only allow same-origin relative paths — never an absolute/external URL.
    if (next && next.startsWith('/') && !next.startsWith('//')) return next;
    return '/dashboard';
  }

  function onSubmit(values: Credentials) {
    setFormError(null);
    login(values, {
      onSuccess: () => router.replace(safeNext()),
      onError: (err) => {
        if (err instanceof ApiError && err.problem.status === 401) {
          setFormError('Invalid email or password.');
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
        <CardTitle>Log in</CardTitle>
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

          <Field id="password" label="Password" error={errors.password?.message}>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              aria-invalid={!!errors.password}
              {...register('password', { required: 'Password is required.' })}
            />
          </Field>

          {formError && (
            <p className="text-small text-red" role="alert">
              {formError}
            </p>
          )}

          <Button type="submit" size="lg" disabled={isPending} className="w-full">
            {isPending ? 'Logging in…' : 'Log in'}
          </Button>
        </form>

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

'use client';

/**
 * Privacy & consent settings (B44) — view and manage DPDP consent per purpose.
 *
 * The consent state is the source of truth on the server (auth.users.dpdp_consents);
 * every toggle calls the grant/revoke writer, which appends to the consent audit log.
 * Educational framing only — no advisory language, no numerics.
 */

import * as React from 'react';
import { toast } from 'sonner';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardBody,
} from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { cn } from '@/lib/cn';
import { useConsent, useGrantConsent, useRevokeConsent } from '@/features/consent/api';
import { purposeCopy } from '@/features/consent/purposeCopy';
import type { ConsentPurpose } from '@/features/consent/types';

// Display order — data-processing purposes first, cross-border transfers last.
const PURPOSE_ORDER: ConsentPurpose[] = [
  'mf_analytics',
  'ai_insights',
  'portfolio_sync',
  'behavioral_nudges',
  'marketing',
  'cross_border_ai',
  'cross_border_notify',
];

// ---------------------------------------------------------------------------
// Toggle — accessible role="switch" styled with tokens (mirrors notifications).
// ---------------------------------------------------------------------------
interface ToggleProps {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label: string;
}

function Toggle({ id, checked, onChange, disabled = false, label }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={cn(
        'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent',
        'transition-colors duration-200',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
        'disabled:pointer-events-none disabled:opacity-40',
        checked ? 'bg-royal' : 'bg-surface-3',
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm',
          'transform transition-transform duration-200',
          checked ? 'translate-x-5' : 'translate-x-0',
        )}
      />
    </button>
  );
}

export default function PrivacyConsentPage() {
  const { data: consent, isLoading, isError, refetch } = useConsent();
  const grant = useGrantConsent();
  const revoke = useRevokeConsent();

  const pending = grant.isPending || revoke.isPending;

  function handleToggle(purpose: ConsentPurpose, next: boolean) {
    const mutation = next ? grant : revoke;
    mutation.mutate(
      { purposes: [purpose] },
      {
        onSuccess: () =>
          toast.success(next ? 'Consent granted' : 'Consent withdrawn'),
        onError: () => toast.error('Could not update your consent. Please try again.'),
      },
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 max-w-2xl">
        <div className="flex flex-col gap-1">
          <Skeleton className="h-7 w-56 rounded-md" />
          <Skeleton className="h-4 w-80 rounded-md" />
        </div>
        <Card>
          <CardBody className="flex flex-col gap-5">
            <Skeleton className="h-14 w-full rounded-md" />
            <Skeleton className="h-14 w-full rounded-md" />
            <Skeleton className="h-14 w-full rounded-md" />
          </CardBody>
        </Card>
      </div>
    );
  }

  if (isError || !consent) {
    return (
      <ErrorCard
        title="Could not load your consent settings"
        message="Check your connection and try again."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      {/* Page heading */}
      <div className="flex flex-col gap-1">
        <h1 className="text-h2 font-medium text-ink">Privacy &amp; consent</h1>
        <p className="text-small text-ink-secondary">
          Choose how DhanRadar may process your data. You can withdraw any consent at
          any time; withdrawal applies to future processing.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Data-use permissions</CardTitle>
          <CardDescription>
            Each permission is requested separately under the DPDP Act. Some features
            are unavailable until the related permission is granted.
          </CardDescription>
        </CardHeader>
        <CardBody className="flex flex-col gap-6">
          {PURPOSE_ORDER.map((purpose, idx) => {
            const copy = purposeCopy[purpose];
            const granted = consent.consents[purpose] ?? false;
            return (
              <div key={purpose} className="flex flex-col gap-3">
                {idx > 0 && <div className="border-t border-line" />}
                <div className="flex items-start justify-between gap-4">
                  <div className="flex flex-col gap-0.5">
                    <label
                      htmlFor={`consent-${purpose}`}
                      className="text-body font-medium text-ink cursor-pointer"
                    >
                      {copy.title}
                    </label>
                    <p className="text-caption text-ink-muted">{copy.description}</p>
                  </div>
                  <Toggle
                    id={`consent-${purpose}`}
                    checked={granted}
                    disabled={pending}
                    onChange={(next) => handleToggle(purpose, next)}
                    label={`${granted ? 'Withdraw consent for' : 'Grant consent for'}: ${copy.title}`}
                  />
                </div>
              </div>
            );
          })}
        </CardBody>
      </Card>
    </div>
  );
}

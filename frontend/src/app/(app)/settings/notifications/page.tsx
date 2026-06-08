'use client';

import * as React from 'react';
import { toast } from 'sonner';
import {
  useNotificationPreferences,
  useUpdateNotificationPreferences,
  useSendTestNotification,
} from '@/features/notifications/api';
import type { PreferencesResponse, PreferencesUpdate } from '@/features/notifications/types';
import { useMe } from '@/features/auth/api';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardBody,
  CardFooter,
} from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, Field } from '@/components/ui/Input';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { ApiError } from '@/lib/apiClient';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TELEGRAM_ID_RE = /^-?\d{1,20}$/;
const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
const PRO_TIERS = ['pro', 'pro_plus', 'founder_lifetime'] as const;

function isProTier(tier: string | undefined): boolean {
  return PRO_TIERS.includes(tier as (typeof PRO_TIERS)[number]);
}

// ---------------------------------------------------------------------------
// Toggle — accessible role="switch" styled with tokens.
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

// ---------------------------------------------------------------------------
// Local form state — tracks edits against the loaded server baseline.
// ---------------------------------------------------------------------------
interface FormState {
  telegramEnabled: boolean;
  emailEnabled: boolean;
  telegramChatId: string;
  quietHoursStart: string;
  quietHoursEnd: string;
}

function prefsToForm(prefs: PreferencesResponse): FormState {
  return {
    telegramEnabled: prefs.channels_enabled['telegram'] ?? false,
    emailEnabled: prefs.channels_enabled['email'] ?? false,
    telegramChatId: prefs.telegram_chat_id ?? '',
    quietHoursStart: prefs.quiet_hours_start ?? '',
    quietHoursEnd: prefs.quiet_hours_end ?? '',
  };
}

function computeDiff(
  form: FormState,
  baseline: PreferencesResponse,
): PreferencesUpdate | null {
  const update: PreferencesUpdate = {};

  // telegram_chat_id — null when cleared, string when set
  const newChatId = form.telegramChatId.trim() === '' ? null : form.telegramChatId.trim();
  if (newChatId !== baseline.telegram_chat_id) {
    update.telegram_chat_id = newChatId;
  }

  // quiet hours — null when cleared
  const newStart = form.quietHoursStart.trim() === '' ? null : form.quietHoursStart;
  const newEnd = form.quietHoursEnd.trim() === '' ? null : form.quietHoursEnd;
  if (newStart !== baseline.quiet_hours_start) update.quiet_hours_start = newStart;
  if (newEnd !== baseline.quiet_hours_end) update.quiet_hours_end = newEnd;

  // channels_enabled — only send if either key changed
  const baselineTelegram = baseline.channels_enabled['telegram'] ?? false;
  const baselineEmail = baseline.channels_enabled['email'] ?? false;
  if (form.telegramEnabled !== baselineTelegram || form.emailEnabled !== baselineEmail) {
    update.channels_enabled = {
      telegram: form.telegramEnabled,
      email: form.emailEnabled,
    };
  }

  return Object.keys(update).length > 0 ? update : null;
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------
function NotificationPreferencesSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Skeleton className="h-7 w-64 rounded-md" />
        <Skeleton className="h-4 w-80 rounded-md" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-24 rounded-md" />
        </CardHeader>
        <CardBody className="flex flex-col gap-5">
          <Skeleton className="h-14 w-full rounded-md" />
          <Skeleton className="h-14 w-full rounded-md" />
          <Skeleton className="h-14 w-full rounded-md" />
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-28 rounded-md" />
        </CardHeader>
        <CardBody className="flex flex-col gap-4">
          <Skeleton className="h-10 w-full rounded-md" />
          <Skeleton className="h-10 w-full rounded-md" />
        </CardBody>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function NotificationPreferencesPage() {
  const { data: prefs, isLoading, isError, refetch } = useNotificationPreferences();
  const { data: me } = useMe();
  const updatePrefs = useUpdateNotificationPreferences();
  const sendTest = useSendTestNotification();

  // Form state — initialised once prefs load; re-synced if prefs data changes
  // (e.g. cache invalidation from another tab).
  const [form, setForm] = React.useState<FormState | null>(null);
  const [telegramIdError, setTelegramIdError] = React.useState<string | undefined>();

  React.useEffect(() => {
    if (prefs) {
      setForm(prefsToForm(prefs));
    }
  }, [prefs]);

  // Patch a single key in form state
  function patch<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
    if (key === 'telegramChatId') setTelegramIdError(undefined);
  }

  function handleSave() {
    if (!form || !prefs) return;

    // Client-side validation for telegram chat ID
    const chatIdValue = form.telegramChatId.trim();
    if (chatIdValue !== '' && !TELEGRAM_ID_RE.test(chatIdValue)) {
      setTelegramIdError('Must be a numeric Telegram chat ID (e.g. 123456789 or -1001234567890).');
      return;
    }

    // Validate quiet hours format if set
    if (form.quietHoursStart && !TIME_RE.test(form.quietHoursStart)) {
      toast.error('Quiet hours start time is invalid.');
      return;
    }
    if (form.quietHoursEnd && !TIME_RE.test(form.quietHoursEnd)) {
      toast.error('Quiet hours end time is invalid.');
      return;
    }

    const diff = computeDiff(form, prefs);
    if (!diff) {
      toast('No changes to save.');
      return;
    }

    updatePrefs.mutate(diff, {
      onSuccess: () => toast.success('Preferences saved'),
      onError: (err) => {
        const detail =
          err instanceof ApiError ? (err.problem.detail ?? 'Could not save') : 'Could not save';
        toast.error(detail);
      },
    });
  }

  function handleClearQuietHours() {
    setForm((prev) =>
      prev ? { ...prev, quietHoursStart: '', quietHoursEnd: '' } : prev,
    );
  }

  function handleSendTest() {
    sendTest.mutate(
      { channel: 'telegram' },
      {
        onSuccess: () => toast.success('Test notification queued'),
        onError: (err) => {
          if (err instanceof ApiError) {
            if (err.problem.detail === 'telegram_not_set') {
              toast.error('Set your Telegram chat ID first');
              return;
            }
          }
          toast.error('Could not send test notification');
        },
      },
    );
  }

  const isPro = isProTier(me?.tier);

  // ---- Render states ----
  if (isLoading || !form) {
    return <NotificationPreferencesSkeleton />;
  }

  if (isError) {
    return (
      <ErrorCard
        title="Could not load preferences"
        message="Check your connection and try again."
        onRetry={() => refetch()}
      />
    );
  }

  // prefs is guaranteed non-undefined here: isLoading=false, isError=false,
  // and form was initialised from prefs in the useEffect above.
  const loadedPrefs = prefs!;

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      {/* Page heading */}
      <div className="flex flex-col gap-1">
        <h1 className="text-h2 font-medium text-ink">Notification preferences</h1>
        <p className="text-small text-ink-secondary">
          Choose how DhanRadar reaches you. All times are IST.
        </p>
      </div>

      {/* Section 1 — Channels */}
      <Card>
        <CardHeader>
          <CardTitle>Channels</CardTitle>
          <CardDescription>Enable the channels you want to receive updates on.</CardDescription>
        </CardHeader>
        <CardBody className="flex flex-col gap-6">
          {/* Telegram */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex flex-col gap-0.5">
                <label
                  htmlFor="toggle-telegram"
                  className="text-body font-medium text-ink cursor-pointer"
                >
                  Telegram
                </label>
                <p className="text-caption text-ink-muted">Receive alerts via Telegram bot.</p>
              </div>
              <Toggle
                id="toggle-telegram"
                checked={form.telegramEnabled}
                onChange={(v) => patch('telegramEnabled', v)}
                label="Enable Telegram notifications"
              />
            </div>
            {/* Telegram chat ID — always visible so users can set it */}
            <Field
              id="telegram-chat-id"
              label="Telegram chat ID"
              error={telegramIdError}
              hint="Find your chat ID via @userinfobot on Telegram."
            >
              <Input
                id="telegram-chat-id"
                inputMode="numeric"
                placeholder="e.g. 123456789"
                value={form.telegramChatId}
                onChange={(e) => patch('telegramChatId', e.target.value)}
                aria-invalid={telegramIdError !== undefined ? true : undefined}
                aria-describedby={
                  telegramIdError ? 'telegram-chat-id-error' : 'telegram-chat-id-hint'
                }
              />
            </Field>
          </div>

          {/* Divider */}
          <div className="border-t border-line" />

          {/* Email */}
          <div className="flex items-center justify-between">
            <div className="flex flex-col gap-0.5">
              <label
                htmlFor="toggle-email"
                className="text-body font-medium text-ink cursor-pointer"
              >
                Email
              </label>
              <div className="flex items-center gap-2">
                <p className="text-caption text-ink-muted">Receive alerts via email.</p>
                {loadedPrefs.email_verified ? (
                  <span className="rounded-full bg-emerald/10 text-emerald text-caption px-2 py-0.5 font-medium">
                    Verified
                  </span>
                ) : (
                  <span className="rounded-full bg-amber/10 text-amber text-caption px-2 py-0.5 font-medium">
                    Unverified
                  </span>
                )}
              </div>
            </div>
            <Toggle
              id="toggle-email"
              checked={form.emailEnabled}
              onChange={(v) => patch('emailEnabled', v)}
              label="Enable email notifications"
            />
          </div>

          {/* Divider */}
          <div className="border-t border-line" />

          {/* WhatsApp — coming soon */}
          <div className="flex items-center justify-between opacity-60">
            <div className="flex flex-col gap-0.5">
              <span className="text-body font-medium text-ink-muted">WhatsApp</span>
              <p className="text-caption text-ink-muted">Coming soon.</p>
            </div>
            <Toggle
              id="toggle-whatsapp"
              checked={false}
              onChange={() => {}}
              disabled
              label="WhatsApp notifications (coming soon)"
            />
          </div>
        </CardBody>
      </Card>

      {/* Section 2 — Quiet hours */}
      <Card>
        <CardHeader>
          <CardTitle>Quiet hours</CardTitle>
          <CardDescription>
            During quiet hours, non-urgent notifications are held and delivered afterward. Security
            alerts always come through.
          </CardDescription>
        </CardHeader>
        <CardBody className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4">
            <Field id="quiet-hours-start" label="Start">
              <Input
                id="quiet-hours-start"
                type="time"
                value={form.quietHoursStart}
                onChange={(e) => patch('quietHoursStart', e.target.value)}
              />
            </Field>
            <Field id="quiet-hours-end" label="End">
              <Input
                id="quiet-hours-end"
                type="time"
                value={form.quietHoursEnd}
                onChange={(e) => patch('quietHoursEnd', e.target.value)}
              />
            </Field>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="self-start"
            onClick={handleClearQuietHours}
            disabled={form.quietHoursStart === '' && form.quietHoursEnd === ''}
          >
            Clear quiet hours
          </Button>
        </CardBody>
      </Card>

      {/* Save footer */}
      <Card>
        <CardFooter className="justify-between flex-wrap gap-3">
          <Button
            type="button"
            variant="primary"
            size="md"
            onClick={handleSave}
            disabled={updatePrefs.isPending}
          >
            {updatePrefs.isPending ? 'Saving…' : 'Save preferences'}
          </Button>
        </CardFooter>
      </Card>

      {/* Test notification — Pro feature */}
      <Card>
        <CardHeader>
          <CardTitle>Send a test notification</CardTitle>
          <CardDescription>
            Verify your Telegram setup is working by sending a test message.
          </CardDescription>
        </CardHeader>
        <CardBody className="flex flex-col gap-2">
          <div className="flex items-center gap-3 flex-wrap">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleSendTest}
              disabled={!isPro || sendTest.isPending}
            >
              {sendTest.isPending ? 'Sending…' : 'Send test to Telegram'}
            </Button>
            {!isPro && (
              <span className="rounded-full bg-amber/10 text-amber text-caption px-2 py-0.5 font-medium">
                Pro
              </span>
            )}
          </div>
          {!isPro && (
            <p className="text-caption text-ink-muted">
              Upgrade to Pro to send test notifications.
            </p>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

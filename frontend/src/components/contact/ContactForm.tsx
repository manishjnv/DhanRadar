'use client';

/**
 * ContactForm — public Contact-Us enquiry form.
 *
 * Posts to POST /api/v1/contact (no auth required, works signed in or out).
 * Client validation mirrors the server's Pydantic limits so the common case
 * never round-trips just to fail; the server remains the source of truth
 * (RFC7807 422 on anything this misses).
 *
 * Honeypot: the `website` field is off-screen (not display:none — some bots
 * skip display:none fields, so this stays in the accessibility tree layout
 * but visually and semantically hidden from real users) and never touched by
 * a human filling the visible fields.
 */
import * as React from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardBody } from '@/components/ui/Card';
import { Field, Input } from '@/components/ui/Input';
import { cn } from '@/lib/cn';
import { api, ApiError } from '@/lib/apiClient';
import { useMe } from '@/features/auth/api';

const TOPICS: { value: string; label: string }[] = [
  { value: 'general', label: 'General question' },
  { value: 'account', label: 'My account' },
  { value: 'data_deletion', label: 'Delete my data' },
  { value: 'feedback', label: 'Feedback' },
  { value: 'partnership', label: 'Partnership' },
  { value: 'other', label: 'Other' },
];

const MESSAGE_MAX = 3000;
const MESSAGE_MIN = 10;
const NAME_MAX = 100;

interface FormState {
  name: string;
  email: string;
  topic: string;
  message: string;
  website: string; // honeypot
}

const INITIAL_STATE: FormState = {
  name: '',
  email: '',
  topic: 'general',
  message: '',
  website: '',
};

type Status = 'idle' | 'submitting' | 'success' | 'rate_limited' | 'unavailable';

function validate(state: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  const name = state.name.trim();
  if (!name) errors.name = 'Enter your name.';
  else if (name.length > NAME_MAX) errors.name = `Name must be ${NAME_MAX} characters or fewer.`;
  else if (/[\r\n]/.test(name)) errors.name = 'Name must be a single line.';

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(state.email.trim())) {
    errors.email = 'Enter a valid email address.';
  }

  const message = state.message.trim();
  if (message.length < MESSAGE_MIN) {
    errors.message = `Message must be at least ${MESSAGE_MIN} characters.`;
  } else if (message.length > MESSAGE_MAX) {
    errors.message = `Message must be ${MESSAGE_MAX} characters or fewer.`;
  }

  return errors;
}

export function ContactForm() {
  const { data: me } = useMe();
  const [state, setState] = React.useState<FormState>(INITIAL_STATE);
  const [errors, setErrors] = React.useState<Record<string, string>>({});
  const [status, setStatus] = React.useState<Status>('idle');
  const prefilledEmail = React.useRef(false);

  React.useEffect(() => {
    if (me?.email && !prefilledEmail.current) {
      setState((s) => ({ ...s, email: me.email }));
      prefilledEmail.current = true;
    }
  }, [me?.email]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setState((s) => ({ ...s, [key]: value }));
    if (errors[key]) setErrors((e) => ({ ...e, [key]: '' }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fieldErrors = validate(state);
    setErrors(fieldErrors);
    if (Object.keys(fieldErrors).length > 0) return;

    setStatus('submitting');
    try {
      await api.post('/contact', {
        name: state.name.trim(),
        email: state.email.trim(),
        topic: state.topic,
        message: state.message.trim(),
        website: state.website,
      });
      setStatus('success');
    } catch (err) {
      if (err instanceof ApiError && err.problem.status === 429) {
        setStatus('rate_limited');
      } else {
        setStatus('unavailable');
      }
    }
  }

  function reset() {
    setState({ ...INITIAL_STATE, email: me?.email ?? '' });
    setErrors({});
    setStatus('idle');
  }

  if (status === 'success') {
    return (
      <Card>
        <CardBody>
          <p role="status" className="text-small text-ink">
            Thanks — we got your message and will reply to {state.email}.
          </p>
          <Button type="button" variant="secondary" className="mt-4" onClick={reset}>
            Send another message
          </Button>
        </CardBody>
      </Card>
    );
  }

  const submitting = status === 'submitting';

  return (
    <Card>
      <CardBody>
        <h2 className="text-h3 font-medium text-ink mb-4">Send us a message</h2>
        <form onSubmit={handleSubmit} noValidate className="relative flex flex-col gap-4">
          <Field id="contact-name" label="Name" error={errors.name}>
            <Input
              value={state.name}
              onChange={(e) => update('name', e.target.value)}
              maxLength={NAME_MAX}
              autoComplete="name"
              disabled={submitting}
            />
          </Field>

          <Field id="contact-email" label="Email" error={errors.email}>
            <Input
              type="email"
              value={state.email}
              onChange={(e) => update('email', e.target.value)}
              autoComplete="email"
              disabled={submitting}
            />
          </Field>

          <Field id="contact-topic" label="Topic">
            <select
              id="contact-topic"
              value={state.topic}
              onChange={(e) => update('topic', e.target.value)}
              disabled={submitting}
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink focus:outline-none focus:ring-2 focus:ring-royal/40 disabled:opacity-50"
            >
              {TOPICS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>

          <div className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between">
              <label htmlFor="contact-message" className="text-small font-medium text-ink">
                Message
              </label>
              <span className="text-caption text-ink-muted tabular-nums">
                {state.message.length} / {MESSAGE_MAX}
              </span>
            </div>
            <textarea
              id="contact-message"
              value={state.message}
              onChange={(e) => update('message', e.target.value.slice(0, MESSAGE_MAX))}
              rows={5}
              maxLength={MESSAGE_MAX}
              disabled={submitting}
              aria-describedby={errors.message ? 'contact-message-error' : undefined}
              aria-invalid={errors.message ? true : undefined}
              className={cn(
                'w-full resize-none rounded-md border bg-surface px-3 py-2 text-small text-ink',
                'placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40',
                'disabled:opacity-50',
                errors.message ? 'border-red focus:ring-red/30' : 'border-line',
              )}
            />
            {errors.message && (
              <p id="contact-message-error" className="text-caption text-red" role="alert">
                {errors.message}
              </p>
            )}
          </div>

          {/* Honeypot — hidden from real users, left for bots that fill every field. */}
          <div className="absolute -left-[9999px] top-auto h-px w-px overflow-hidden">
            <label htmlFor="contact-website">Website</label>
            <input
              id="contact-website"
              name="website"
              type="text"
              value={state.website}
              onChange={(e) => update('website', e.target.value)}
              tabIndex={-1}
              autoComplete="off"
              aria-hidden="true"
            />
          </div>

          <p className="text-caption text-ink-muted">
            We use your name and email only to reply to you. Don&apos;t include
            passwords, OTPs, full PAN or bank details.
          </p>

          {status === 'rate_limited' && (
            <p role="alert" className="text-caption text-red">
              You&apos;ve sent a few messages already. Please wait a few
              minutes, or email{' '}
              <a href="mailto:connect@dhanradar.com" className="underline underline-offset-2">
                connect@dhanradar.com
              </a>
              .
            </p>
          )}

          {status === 'unavailable' && (
            <p role="alert" className="text-caption text-red">
              We couldn&apos;t send your message right now. Please email{' '}
              <a href="mailto:connect@dhanradar.com" className="underline underline-offset-2">
                connect@dhanradar.com
              </a>
              .
            </p>
          )}

          <Button type="submit" disabled={submitting} className="self-start">
            {submitting ? 'Sending…' : 'Send message'}
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

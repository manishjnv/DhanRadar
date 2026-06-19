'use client';

/**
 * ConfirmDialog — shared confirm / step-up dialog for Phase-5 gated mutations.
 *
 * Four-state contract: idle → submitting (button spinner + disabled) →
 *   error (inline error box + Retry) → success (auto-close + refetch via onSuccess).
 * Optimistic-free: no UI change until the server response is confirmed.
 *
 * Props:
 *   open              — controlled open state
 *   onClose           — close callback (called on cancel, ESC, backdrop click, or success)
 *   title             — dialog heading
 *   description       — body copy (ReactNode; can include <strong> for emphasis)
 *   confirmLabel      — text on the confirm button (default "Confirm")
 *   confirmVariant    — button variant (default "primary"; use "danger" for destructive actions)
 *   onConfirm         — async handler; must resolve on success, throw ApiError/Error on failure
 *   confirmPhrase     — when set the confirm button is disabled until the user types this exactly
 *                       (use for ALL destructive mutations)
 *   children          — optional additional form fields rendered above the type-to-confirm input
 *
 * Token rules: royal (#1E5EFF), bg-surface, border-line, text-ink,
 *   bg-red for danger, no inter/manrope/hardcoded colours.
 */

import * as React from 'react';
import { X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';
import { ApiError } from '@/lib/apiClient';

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------
type DialogState = 'idle' | 'submitting' | 'error' | 'success';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
export interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description: React.ReactNode;
  confirmLabel?: string;
  confirmVariant?: 'primary' | 'danger' | 'secondary' | 'ghost' | 'outline';
  onConfirm: () => Promise<void>;
  /** When set, the confirm button stays disabled until the user types this exact string. */
  confirmPhrase?: string;
  /** Optional additional fields rendered between description and the type-to-confirm input. */
  children?: React.ReactNode;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function ConfirmDialog({
  open,
  onClose,
  title,
  description,
  confirmLabel = 'Confirm',
  confirmVariant = 'primary',
  onConfirm,
  confirmPhrase,
  children,
}: ConfirmDialogProps) {
  const [state, setState] = React.useState<DialogState>('idle');
  const [errorMsg, setErrorMsg]   = React.useState<string>('');
  const [phraseInput, setPhraseInput] = React.useState('');

  // Reset internal state when dialog opens/closes
  React.useEffect(() => {
    if (!open) {
      setState('idle');
      setErrorMsg('');
      setPhraseInput('');
    }
  }, [open]);

  // ESC to close
  React.useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && state !== 'submitting') onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, state, onClose]);

  if (!open) return null;

  const phraseMatch = !confirmPhrase || phraseInput === confirmPhrase;
  const canSubmit = state !== 'submitting' && phraseMatch;

  async function handleConfirm() {
    if (!canSubmit) return;
    setState('submitting');
    setErrorMsg('');
    try {
      await onConfirm();
      setState('success');
      // Brief success flash then close
      setTimeout(() => {
        onClose();
      }, 400);
    } catch (err) {
      let detail = 'An unexpected error occurred. Please retry.';
      if (err instanceof ApiError) {
        detail = err.problem.detail ?? err.problem.title ?? detail;
      } else if (err instanceof Error) {
        detail = err.message;
      }
      setErrorMsg(detail);
      setState('error');
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-overlay bg-black/50"
        aria-hidden="true"
        onClick={() => { if (state !== 'submitting') onClose(); }}
      />

      {/* Dialog panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-desc"
        className={cn(
          'fixed left-1/2 top-1/2 z-modal w-full max-w-md -translate-x-1/2 -translate-y-1/2',
          'rounded-xl bg-surface border border-line shadow-xl',
          'flex flex-col',
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
          <h2 id="confirm-dialog-title" className="text-h3 font-medium text-ink">
            {title}
          </h2>
          <button
            type="button"
            onClick={() => { if (state !== 'submitting') onClose(); }}
            disabled={state === 'submitting'}
            aria-label="Close dialog"
            className="flex items-center justify-center rounded-md p-1.5 text-ink-secondary hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 disabled:opacity-40"
          >
            <X size={16} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-col gap-4 px-5 py-5">
          {/* Description */}
          <p id="confirm-dialog-desc" className="text-small text-ink-secondary leading-relaxed">
            {description}
          </p>

          {/* Optional extra fields (form inputs for body params) */}
          {children && (
            <div className="flex flex-col gap-3">
              {children}
            </div>
          )}

          {/* Type-to-confirm */}
          {confirmPhrase && (
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="confirm-phrase-input"
                className="text-small font-medium text-ink"
              >
                Type{' '}
                <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-caption text-ink border border-line">
                  {confirmPhrase}
                </code>{' '}
                to confirm
              </label>
              <input
                id="confirm-phrase-input"
                type="text"
                autoComplete="off"
                value={phraseInput}
                onChange={(e) => setPhraseInput(e.target.value)}
                disabled={state === 'submitting'}
                placeholder={confirmPhrase}
                className={cn(
                  'w-full rounded-md border bg-surface px-3 py-2 text-small text-ink',
                  'placeholder:text-ink-muted font-mono',
                  'focus:outline-none focus:ring-2 focus:ring-royal/40',
                  'disabled:opacity-50',
                  phraseInput && !phraseMatch ? 'border-red focus:ring-red/30' : 'border-line',
                )}
              />
            </div>
          )}

          {/* Error box */}
          {state === 'error' && (
            <div
              role="alert"
              className="rounded-md border border-red/30 bg-red/5 px-4 py-3 text-small text-red"
            >
              <p className="font-medium">Action failed</p>
              <p className="mt-0.5 text-caption">{errorMsg}</p>
            </div>
          )}

          {/* Success flash */}
          {state === 'success' && (
            <div className="rounded-md border border-emerald/30 bg-emerald/5 px-4 py-3 text-small text-emerald">
              Done — refreshing…
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-line px-5 py-4">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={onClose}
            disabled={state === 'submitting'}
          >
            Cancel
          </Button>
          {state === 'error' ? (
            <Button
              type="button"
              size="sm"
              variant={confirmVariant}
              onClick={handleConfirm}
              disabled={!canSubmit}
            >
              Retry
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              variant={confirmVariant}
              onClick={handleConfirm}
              disabled={!canSubmit}
              aria-busy={state === 'submitting'}
            >
              {state === 'submitting' ? (
                <>
                  <Loader2 size={13} strokeWidth={2} className="animate-spin" aria-hidden="true" />
                  {confirmLabel}…
                </>
              ) : (
                confirmLabel
              )}
            </Button>
          )}
        </div>
      </div>
    </>
  );
}

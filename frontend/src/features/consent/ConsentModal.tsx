'use client';

/**
 * ConsentModal — point-of-use DPDP consent capture dialog.
 *
 * Accessibility contract:
 *  - role="dialog" aria-modal="true" aria-labelledby heading id
 *  - Focus is moved to the heading on open
 *  - Escape key fires onCancel
 *  - "Grant & continue" is disabled until the "I consent" checkbox is checked
 *
 * Styling uses canonical tokens only (bg-surface, border-line, text-ink, etc.).
 * No advisory verbs. No numerics in the DOM.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';
import { Button } from '@/components/ui/Button';
import { Disclaimer } from '@/components/ui/Disclaimer';
import { useGrantConsent } from './api';
import { purposeCopy } from './purposeCopy';
import type { ConsentPurpose } from './types';

export interface ConsentModalProps {
  open: boolean;
  purposes: ConsentPurpose[];
  onGranted: () => void;
  onCancel: () => void;
}

export function ConsentModal({ open, purposes, onGranted, onCancel }: ConsentModalProps) {
  const [checked, setChecked] = React.useState(false);
  const headingRef = React.useRef<HTMLHeadingElement>(null);
  const grantConsent = useGrantConsent();

  // Reset checkbox state when the modal opens with new purposes
  React.useEffect(() => {
    if (open) {
      setChecked(false);
    }
  }, [open]);

  // Move focus to the heading when the modal opens
  React.useEffect(() => {
    if (open && headingRef.current) {
      headingRef.current.focus();
    }
  }, [open]);

  // Escape key → onCancel
  React.useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onCancel();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onCancel]);

  function handleGrant() {
    if (!checked || purposes.length === 0) return;
    grantConsent.mutate(
      { purposes },
      {
        onSuccess: () => onGranted(),
      },
    );
  }

  if (!open) return null;

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      aria-hidden={!open}
    >
      {/* Scrim */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Dialog panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="consent-modal-heading"
        className={cn(
          'relative z-10 w-full max-w-md mx-4',
          'bg-surface border border-line rounded-lg shadow-lg',
          'flex flex-col gap-0',
        )}
      >
        {/* Header */}
        <div className="flex flex-col gap-1 border-b border-line px-6 py-4">
          <h2
            id="consent-modal-heading"
            ref={headingRef}
            tabIndex={-1}
            className="text-h3 font-medium text-ink leading-snug focus:outline-none"
          >
            Data use permission required
          </h2>
          <p className="text-small text-ink-secondary">
            To continue, DhanRadar needs your permission to process your data for the
            following purpose{purposes.length !== 1 ? 's' : ''}.
          </p>
        </div>

        {/* Purpose list */}
        <div className="px-6 py-4 flex flex-col gap-4">
          {purposes.map((purpose) => {
            const copy = purposeCopy[purpose];
            return (
              <div key={purpose} className="flex flex-col gap-0.5">
                <p className="text-body font-medium text-ink">{copy.title}</p>
                <p className="text-small text-ink-secondary">{copy.description}</p>
              </div>
            );
          })}
        </div>

        {/* Consent checkbox */}
        <div className="px-6 pb-4">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              id="consent-modal-checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
              className={cn(
                'mt-0.5 h-4 w-4 shrink-0 rounded border border-line-strong',
                'accent-royal',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
              )}
            />
            <span className="text-small text-ink">
              I have read and understood the above. I consent to DhanRadar processing my
              data for the stated purpose{purposes.length !== 1 ? 's' : ''}.
            </span>
          </label>
        </div>

        {/* Disclaimer */}
        <div className="px-6 pb-4">
          <Disclaimer />
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-end gap-3 border-t border-line px-6 py-3">
          <Button
            type="button"
            variant="ghost"
            size="md"
            onClick={onCancel}
            disabled={grantConsent.isPending}
          >
            Not now
          </Button>
          <Button
            type="button"
            variant="primary"
            size="md"
            onClick={handleGrant}
            disabled={!checked || grantConsent.isPending}
          >
            {grantConsent.isPending ? 'Saving…' : 'Grant & continue'}
          </Button>
        </div>
      </div>
    </div>
  );
}

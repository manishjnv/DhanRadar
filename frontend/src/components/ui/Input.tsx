import * as React from 'react';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Input — canonical token-styled text field.
// Mirrors the inline input previously hand-rolled in the CAS upload page so
// every form field shares one focus-ring / border / disabled treatment.
// `aria-invalid` flips the border to the danger token for validation errors.
// ---------------------------------------------------------------------------

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          'w-full rounded-md border bg-surface px-3 py-2 text-small text-ink',
          'placeholder:text-ink-muted',
          'focus:outline-none focus:ring-2 focus:ring-royal/40',
          'disabled:opacity-50',
          'aria-[invalid=true]:border-red aria-[invalid=true]:focus:ring-red/30',
          'border-line',
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = 'Input';

// ---------------------------------------------------------------------------
// Field — label + input + error wrapper. Wires htmlFor/id and the
// aria-describedby → error association so screen readers announce the message.
// ---------------------------------------------------------------------------

export interface FieldProps {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}

export function Field({ id, label, error, hint, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-small font-medium text-ink">
        {label}
      </label>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-caption text-ink-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-caption text-red" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

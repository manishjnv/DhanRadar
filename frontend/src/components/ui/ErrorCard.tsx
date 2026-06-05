import * as React from 'react';
import { cn } from '@/lib/cn';
import { Button } from './Button';

export interface ErrorCardProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorCard({
  title = 'Something went wrong',
  message,
  onRetry,
  className,
}: ErrorCardProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border border-line bg-surface p-6 text-center',
        className,
      )}
    >
      <span className="text-2xl" aria-hidden="true">⚠</span>
      <p className="text-body font-medium text-ink">{title}</p>
      {message && <p className="text-small text-ink-muted">{message}</p>}
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

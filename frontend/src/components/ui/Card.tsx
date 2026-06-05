import * as React from 'react';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Card — surface/line token base.
// bg-surface border-line rounded-lg shadow-sm
// ---------------------------------------------------------------------------

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Card({ className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'bg-surface border border-line rounded-lg shadow-sm',
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-1 border-b border-line px-6 py-4',
        className,
      )}
      {...props}
    />
  );
}

export function CardTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    // Generic title wrapper — content is supplied by the caller via children.
    // eslint-disable-next-line jsx-a11y/heading-has-content
    <h3
      className={cn('text-h3 font-medium text-ink leading-snug', className)}
      {...props}
    />
  );
}

export function CardDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn('text-small text-ink-secondary', className)}
      {...props}
    />
  );
}

export function CardBody({ className, ...props }: CardProps) {
  return <div className={cn('px-6 py-4', className)} {...props} />;
}

export function CardFooter({ className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'flex items-center border-t border-line px-6 py-3',
        className,
      )}
      {...props}
    />
  );
}

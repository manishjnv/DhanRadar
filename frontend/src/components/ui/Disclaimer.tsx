import * as React from 'react';
import { cn } from '@/lib/cn';

/**
 * NOT_ADVICE disclaimer — required on every screen that renders a label,
 * score surface, or AI output (architecture non-negotiable #9).
 */
export function Disclaimer({ className }: { className?: string }) {
  return (
    <p
      role="note"
      className={cn('text-caption text-ink-muted', className)}
    >
      Educational information, not investment advice. DhanRadar is a research
      analytics product. SEBI registration does not guarantee accuracy.
    </p>
  );
}

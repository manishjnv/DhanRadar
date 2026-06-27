'use client';

/**
 * HelpTip — one styled tooltip primitive for every page.
 *
 * Replaces three ad-hoc variants:
 *   - funddetail/parts.tsx InfoTip (button + native title=)
 *   - calculators/ui.tsx RangeField inline span (not focusable — a11y bug)
 *   - admin eval page <span cursor-help title=>
 *
 * No new dependency. CSS transition only. ~40 lines of logic.
 * ponytail: simple fixed-side positioning; add collision/flip only at the i18n pass.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';

export interface HelpTipProps {
  tip: string;
  children?: React.ReactNode;
  className?: string;
  side?: 'top' | 'bottom';
}

export function HelpTip({ tip, children, className, side = 'top' }: HelpTipProps) {
  const [visible, setVisible] = React.useState(false);
  const id = React.useId();
  const tooltipId = `helptip-${id}`;

  const show = () => setVisible(true);
  const hide = () => setVisible(false);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') setVisible(false);
  };

  const isTop = side === 'top';

  return (
    <span className={cn('relative inline-flex items-center', className)}>
      <button
        type="button"
        aria-describedby={tooltipId}
        className={cn(
          'inline-grid cursor-help place-items-center rounded-full',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
          // Default (i) bubble — overridden when children are passed
          !children && 'h-[15px] w-[15px] bg-surface-3 text-[9px] font-bold text-ink-muted',
        )}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onKeyDown={handleKeyDown}
      >
        {children ?? 'i'}
      </button>

      {/* Tooltip surface */}
      <span
        id={tooltipId}
        role="tooltip"
        className={cn(
          'pointer-events-none absolute left-1/2 z-50 w-max max-w-[240px]',
          'rounded-lg border border-line bg-surface px-2.5 py-1.5',
          'text-caption text-ink shadow-md',
          '-translate-x-1/2 transition-[opacity,transform]',
          'motion-reduce:transition-none',
          // Side positioning
          isTop
            ? 'bottom-[calc(100%+6px)] origin-bottom'
            : 'top-[calc(100%+6px)] origin-top',
          // Visible state
          visible
            ? 'opacity-100 translate-y-0 duration-150 ease-out'
            : cn(
                'opacity-0 duration-100 ease-in',
                isTop ? 'translate-y-1' : '-translate-y-1',
              ),
        )}
      >
        {tip}
      </span>
    </span>
  );
}

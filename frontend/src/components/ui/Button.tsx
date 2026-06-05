import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Variants use canonical token classes only.
// - Primary action:  royal (brand CTA colour, NOT bg-blue — bg-blue is banned)
// - Secondary/ghost: surface-2 / surface-3 with line border
// - Outline:         transparent bg, line-strong border
// - Danger:          red (accent.red — #E5484D)
// ink-2 is NOT a valid token — use ink-secondary.
// ---------------------------------------------------------------------------
const buttonVariants = cva(
  // Base styles
  [
    'inline-flex items-center justify-center gap-2',
    'rounded-md font-medium transition-colors',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
    'disabled:pointer-events-none disabled:opacity-50',
  ],
  {
    variants: {
      variant: {
        primary:
          'bg-royal text-white hover:bg-royal/90 active:bg-royal/80',
        secondary:
          'bg-surface-2 border border-line text-ink hover:bg-surface-3 active:bg-surface-3',
        ghost:
          'bg-surface-2 border border-line text-ink-secondary hover:bg-surface-3',
        outline:
          'border border-line-strong text-ink hover:bg-surface-2 active:bg-surface-3',
        danger:
          'bg-red text-white hover:bg-red/90 active:bg-red/80',
      },
      size: {
        sm: 'h-8  px-3 text-small',
        md: 'h-10 px-4 text-body',
        lg: 'h-12 px-6 text-h3',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size:    'md',
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = 'Button';

import { cva, type VariantProps } from 'class-variance-authority';
import { Slot } from '@radix-ui/react-slot';
import { cn } from '@/lib/cn';

const button = cva(
  'inline-flex items-center justify-center gap-1.5 rounded-md font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/40 disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        primary: 'bg-blue text-white shadow-sm hover:bg-blue-700',
        dark: 'bg-ink text-bg hover:opacity-90',
        ghost: 'bg-surface-2 border border-line hover:bg-surface-3',
        outline: 'border border-line-strong hover:bg-surface-2',
        success: 'bg-positive text-white',
        danger: 'bg-negative text-white',
      },
      size: { sm: 'h-8 px-3 text-xs', md: 'h-10 px-4 text-sm', lg: 'h-12 px-5 text-base' },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {
  asChild?: boolean; loading?: boolean;
}
export function Button({ className, variant, size, asChild, loading, children, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : 'button';
  return (
    <Comp className={cn(button({ variant, size }), className)} aria-busy={loading} {...props}>
      {loading ? <span className="animate-spin">◌</span> : children}
    </Comp>
  );
}

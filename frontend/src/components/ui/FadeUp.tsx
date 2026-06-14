import * as React from 'react';

interface FadeUpProps {
  children: React.ReactNode;
  delay?: number; // ms
  className?: string;
}

export function FadeUp({ children, delay = 0, className }: FadeUpProps) {
  return (
    <div
      className={['animate-fade-up', className].filter(Boolean).join(' ')}
      style={delay > 0 ? { animationDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  );
}

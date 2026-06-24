/**
 * FundAvatar — deterministic colour block from the scheme name.
 * Shared by the explorer table and card grid so both surfaces match.
 * Uses brand CSS vars (mirrors the original inline avatar) — no hardcoded
 * brand hex in markup.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';

const AVATAR_VAR_COLORS = [
  'var(--dr-navy,#0B1F3A)',
  'var(--dr-royal,#1E5EFF)',
  '#003E80',
  '#006B7D',
  '#1B4332',
  '#6A1B9A',
  '#B71C1C',
  '#374151',
] as const;

export function FundAvatar({
  name,
  size = 'sm',
  className,
}: {
  name: string;
  size?: 'sm' | 'md';
  className?: string;
}) {
  const idx = ((name.charCodeAt(0) || 0) + (name.charCodeAt(1) || 0)) % AVATAR_VAR_COLORS.length;
  return (
    <div
      className={cn(
        'rounded-lg flex items-center justify-center text-white font-bold shrink-0 select-none',
        size === 'md' ? 'w-10 h-10 text-small' : 'w-8 h-8 text-caption',
        className,
      )}
      style={{ background: AVATAR_VAR_COLORS[idx] }}
      aria-hidden="true"
    >
      {name[0]?.toUpperCase() ?? '?'}
    </div>
  );
}

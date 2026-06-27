'use client';

/**
 * DataState — no-suppress render gate.
 *
 * Wraps the four lifecycle states for any data-backed section.
 * Callers pass the envelope status; this component owns the copy decisions.
 * NEVER returns null / collapses the section (founder rule 2026-06-25).
 *
 * ponytail: one gate, composes existing EmptyState/ErrorCard/Skeleton — no new visuals.
 */

import * as React from 'react';
import type { DataStatus, DataReason } from './dataState.types';
import { Skeleton } from './Skeleton';
import { EmptyState } from './EmptyState';
import { ErrorCard } from './ErrorCard';

export type { DataStatus, DataReason };

export interface DataStateProps {
  status: DataStatus;
  reason?: DataReason;
  emptyCopy?: string;
  tierCopy?: string;
  onRetry?: () => void;
  children: React.ReactNode;
  skeleton?: React.ReactNode;
}

function emptyTitle(reason: DataReason | undefined, tierCopy: string | undefined): string {
  if (reason === 'gated' || reason === 'refused') return 'Not available';
  if (reason === 'tier') return tierCopy ?? 'Available on DhanRadar Plus';
  return 'Nothing here yet.';
}

function emptyDescription(reason: DataReason | undefined, emptyCopy: string | undefined): string | undefined {
  if (reason === 'gated' || reason === 'refused') return undefined;
  if (reason === 'tier') return undefined;
  return emptyCopy;
}

export function DataState({
  status,
  reason,
  emptyCopy,
  tierCopy,
  onRetry,
  children,
  skeleton,
}: DataStateProps) {
  if (status === 'loading') {
    return <>{skeleton ?? <Skeleton className="h-24 w-full" />}</>;
  }

  if (status === 'error') {
    return <ErrorCard onRetry={onRetry} />;
  }

  if (status === 'empty' || status === 'withheld') {
    return (
      <EmptyState
        title={emptyTitle(reason, tierCopy)}
        description={emptyDescription(reason, emptyCopy)}
      />
    );
  }

  // status === 'present'
  return <>{children}</>;
}

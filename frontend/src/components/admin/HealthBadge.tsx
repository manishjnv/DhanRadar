import * as React from 'react';
import { cn } from '@/lib/cn';

export type BadgeStatus =
  | 'Healthy'
  | 'Warning'
  | 'Failed'
  | 'Critical'
  | 'Paused'
  | 'Planned'
  | 'Running'
  | 'Success'
  | 'Skipped'
  | 'Bot-Blocked'
  | 'ok'
  | 'warning'
  | 'critical';

const STATUS_CLASSES: Record<BadgeStatus, string> = {
  Healthy:      'bg-emerald/10 text-emerald border-transparent',
  Success:      'bg-emerald/10 text-emerald border-transparent',
  ok:           'bg-emerald/10 text-emerald border-transparent',
  Warning:      'bg-amber/10 text-amber border-transparent',
  Skipped:      'bg-amber/10 text-amber border-transparent',
  warning:      'bg-amber/10 text-amber border-transparent',
  Failed:       'bg-red/10 text-red border-transparent',
  Critical:     'bg-red/10 text-red border-transparent',
  critical:     'bg-red/10 text-red border-transparent',
  'Bot-Blocked':'bg-red/10 text-red border-transparent',
  Paused:       'bg-surface-2 text-ink-muted border border-line',
  Planned:      'bg-surface text-ink-muted border border-line',
  Running:      'bg-royal/10 text-royal border-transparent',
};

const STATUS_LABELS: Record<BadgeStatus, string> = {
  Healthy:      'Healthy',
  Success:      'Success',
  ok:           'OK',
  Warning:      'Warning',
  Skipped:      'Skipped',
  warning:      'Warning',
  Failed:       'Failed',
  Critical:     'Critical',
  critical:     'Critical',
  'Bot-Blocked':'Bot-Blocked',
  Paused:       'Paused',
  Planned:      'Planned',
  Running:      'Running',
};

export interface HealthBadgeProps {
  status: BadgeStatus;
  className?: string;
}

export function HealthBadge({ status, className }: HealthBadgeProps) {
  const isRunning = status === 'Running';
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-caption font-medium',
        STATUS_CLASSES[status] ?? 'bg-surface-2 text-ink-muted',
        className,
      )}
    >
      {isRunning && (
        <span className="h-1.5 w-1.5 rounded-full bg-royal animate-pulse" aria-hidden="true" />
      )}
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

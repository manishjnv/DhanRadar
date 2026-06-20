import * as React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Circle } from 'lucide-react';
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
  | 'Partial'
  | 'ok'
  | 'warning'
  | 'critical';

const STATUS_CLASSES: Record<BadgeStatus, string> = {
  Healthy:      'bg-emerald/10 text-emerald border-transparent',
  Success:      'bg-emerald/10 text-emerald border-transparent',
  ok:           'bg-emerald/10 text-emerald border-transparent',
  Warning:      'bg-amber/10 text-amber border-transparent',
  Skipped:      'bg-amber/10 text-amber border-transparent',
  Partial:      'bg-amber/10 text-amber border-transparent',
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
  Partial:      'Partial',
  warning:      'Warning',
  Failed:       'Failed',
  Critical:     'Critical',
  critical:     'Critical',
  'Bot-Blocked':'Bot-Blocked',
  Paused:       'Paused',
  Planned:      'Planned',
  Running:      'Running',
};

/** Returns the lucide icon component for a status group, or null for Running (uses pulsing dot). */
function statusIcon(status: BadgeStatus): React.ElementType | null {
  switch (status) {
    case 'Healthy':
    case 'Success':
    case 'ok':
      return CheckCircle2;
    case 'Warning':
    case 'Skipped':
    case 'Partial':
    case 'warning':
      return AlertTriangle;
    case 'Failed':
    case 'Critical':
    case 'critical':
    case 'Bot-Blocked':
      return XCircle;
    case 'Paused':
    case 'Planned':
      return Circle;
    case 'Running':
      return null; // handled by pulsing dot below
    default:
      return null;
  }
}

export interface HealthBadgeProps {
  status: BadgeStatus;
  className?: string;
}

export function HealthBadge({ status, className }: HealthBadgeProps) {
  const isRunning = status === 'Running';
  const Icon = statusIcon(status);

  return (
    <span
      role="status"
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-caption font-medium',
        STATUS_CLASSES[status] ?? 'bg-surface-2 text-ink-muted',
        className,
      )}
    >
      {isRunning && (
        <span className="h-1.5 w-1.5 rounded-full bg-royal animate-pulse" aria-hidden="true" />
      )}
      {!isRunning && Icon && (
        <Icon size={11} strokeWidth={2} aria-hidden="true" className="shrink-0" />
      )}
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

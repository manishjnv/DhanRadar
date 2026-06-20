import * as React from 'react';
import { AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatRelative } from '@/components/admin/utils';

export interface AdminAlert {
  type: string;
  message: string;
  severity: 'info' | 'warning' | 'critical';
  created_at: string;
}

interface AlertListProps {
  alerts: AdminAlert[];
}

const SEVERITY_CLASSES: Record<string, string> = {
  info:     'bg-royal/10 text-royal',
  warning:  'bg-amber/10 text-amber',
  critical: 'bg-red/10 text-red',
};

const SEVERITY_ICON: Record<string, React.ElementType> = {
  info:     Info,
  warning:  AlertTriangle,
  critical: AlertCircle,
};

export function AlertList({ alerts }: AlertListProps) {
  if (alerts.length === 0) {
    return <p className="text-small text-ink-muted py-4 text-center">Alerting is not yet active — alerts will appear here once wired.</p>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {alerts.map((alert, i) => {
        const Icon = SEVERITY_ICON[alert.severity] ?? Info;
        return (
          <li
            key={i}
            className={cn(
              'flex items-start gap-3 rounded-lg p-3',
              SEVERITY_CLASSES[alert.severity] ?? 'bg-surface-2 text-ink-secondary',
            )}
          >
            <Icon size={15} strokeWidth={2} className="mt-0.5 shrink-0" aria-hidden="true" />
            <div className="flex-1 min-w-0">
              <p className="text-small font-medium leading-snug">{alert.message}</p>
              <p className="text-caption mt-0.5 opacity-70">
                {alert.type} · {formatRelative(alert.created_at)}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

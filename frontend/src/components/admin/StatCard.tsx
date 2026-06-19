import * as React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Card } from '@/components/ui/Card';

export type StatCardStatus = 'healthy' | 'warning' | 'critical' | 'neutral';
export type StatCardTrend  = 'up' | 'down' | 'flat';

export interface StatCardProps {
  title: string;
  value: React.ReactNode;
  /** Optional secondary label below value */
  sub?: string;
  trend?: StatCardTrend;
  status?: StatCardStatus;
  className?: string;
}

const STATUS_VALUE_CLASS: Record<StatCardStatus, string> = {
  healthy:  'text-ink',
  warning:  'text-amber',
  critical: 'text-red',
  neutral:  'text-ink',
};

const TREND_ICON: Record<StatCardTrend, React.ElementType> = {
  up:   TrendingUp,
  down: TrendingDown,
  flat: Minus,
};

const TREND_CLASS: Record<StatCardTrend, string> = {
  up:   'text-emerald',
  down: 'text-red',
  flat: 'text-ink-muted',
};

export function StatCard({
  title,
  value,
  sub,
  trend,
  status = 'neutral',
  className,
}: StatCardProps) {
  const TrendIcon = trend ? TREND_ICON[trend] : null;

  return (
    <Card className={cn('flex flex-col gap-2 p-5', className)}>
      <p className="text-caption uppercase tracking-wide text-ink-muted">{title}</p>
      <div className="flex items-end justify-between gap-2">
        <span
          className={cn(
            'font-mono text-h2 font-medium tabular-nums',
            STATUS_VALUE_CLASS[status],
          )}
        >
          {value}
        </span>
        {TrendIcon && (
          <TrendIcon
            size={18}
            strokeWidth={2}
            className={cn('mb-1 shrink-0', TREND_CLASS[trend!])}
            aria-hidden="true"
          />
        )}
      </div>
      {sub && <p className="text-caption text-ink-muted">{sub}</p>}
    </Card>
  );
}

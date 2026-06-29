'use client';

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import type { SignalRules } from '@/features/signal/types';

const inrFmt = (n: number) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(n);

interface PortfolioContextProps {
  hasCAS: boolean;
  rules: SignalRules | undefined;
  portfolioValue?: number;
  gainPct?: number;
  drawdownPct?: number;
  fundsInCorrection?: number;
  isLoading?: boolean;
}

export function PortfolioContext({
  hasCAS,
  rules,
  portfolioValue,
  gainPct,
  drawdownPct,
  fundsInCorrection,
  isLoading = false,
}: PortfolioContextProps) {
  if (!hasCAS) {
    return (
      <div className="card-pad">
        <p className="text-small font-medium text-ink">Portfolio context</p>
        <div className="mt-3 flex flex-col items-center gap-3 rounded-lg border border-line bg-surface-2 py-6 text-center">
          <p className="text-small text-ink-muted">
            Upload your CAS to see portfolio context here.
          </p>
          <Link
            href="/mf/portfolio"
            className="rounded-lg bg-royal px-4 py-2 text-small font-medium text-white hover:opacity-90 transition-opacity"
          >
            Upload CAS
          </Link>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="card-pad animate-pulse space-y-3">
        <div className="h-3 w-32 rounded bg-surface-2" />
        <div className="h-2 w-full rounded-full bg-surface-2" />
        <div className="h-16 w-full rounded bg-surface-2" />
      </div>
    );
  }

  const ladder = rules?.deploy_ladder ?? [20, 20, 20, 20, 20];

  return (
    <div className="card-pad flex flex-col gap-3">
      <p className="text-small font-medium text-ink">Portfolio context</p>

      {/* Stats table */}
      <table className="dt">
        <tbody>
          {portfolioValue !== undefined && (
            <tr>
              <td className="text-ink-muted">Current value</td>
              <td className="right mono font-medium text-ink">
                {inrFmt(portfolioValue)}
              </td>
            </tr>
          )}
          {gainPct !== undefined && (
            <tr>
              <td className="text-ink-muted">Overall gain</td>
              <td
                className={cn(
                  'right mono font-medium',
                  gainPct >= 0 ? 'text-emerald' : 'text-red',
                )}
              >
                {gainPct >= 0 ? '+' : ''}
                {gainPct.toFixed(1)}%
              </td>
            </tr>
          )}
          {drawdownPct !== undefined && (
            <tr>
              <td className="text-ink-muted">Drawdown from peak</td>
              <td className="right mono font-medium text-red">
                -{Math.abs(drawdownPct).toFixed(1)}%
              </td>
            </tr>
          )}
          {fundsInCorrection !== undefined && (
            <tr>
              <td className="text-ink-muted">Funds in correction</td>
              <td className="right mono font-medium text-amber">
                {fundsInCorrection}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Deployment ladder */}
      <div>
        <p className="mb-2 text-caption font-medium uppercase tracking-wide text-ink-muted">
          Deployment ladder
        </p>
        <div className="flex flex-col gap-1.5">
          {ladder.map((pct, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-12 shrink-0 text-caption text-ink-muted">S{i + 1}</span>
              <div className="ladder-bar flex-1">
                <div
                  className="ladder-bar-fill"
                  style={{ width: `${pct}%` }}
                  aria-label={`Signal ${i + 1}: ${pct}%`}
                />
              </div>
              <span className="mono w-8 text-right text-caption text-ink-secondary">
                {pct}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

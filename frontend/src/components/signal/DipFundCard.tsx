'use client';

import * as React from 'react';
import { useSignalDipFund, useAddDipFund } from '@/features/signal/api';
import type { SignalRules } from '@/features/signal/types';

const inrFmt = (n: number) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(n);

interface DipFundCardProps {
  rules: SignalRules | undefined;
}

export function DipFundCard({ rules }: DipFundCardProps) {
  const { data: fund, isLoading } = useSignalDipFund();
  const addCash = useAddDipFund();
  const [showAdd, setShowAdd] = React.useState(false);
  const [addAmount, setAddAmount] = React.useState('');

  const ladder = rules?.deploy_ladder ?? [20, 20, 20, 20, 20];

  async function handleAdd() {
    const amount = parseFloat(addAmount);
    if (isNaN(amount) || amount <= 0) return;
    await addCash.mutateAsync(amount);
    setAddAmount('');
    setShowAdd(false);
  }

  if (isLoading) {
    return (
      <div className="card-pad animate-pulse space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="h-16 rounded bg-surface-2" />
          <div className="h-16 rounded bg-surface-2" />
        </div>
        <div className="h-24 rounded bg-surface-2" />
      </div>
    );
  }

  const balance = fund?.balance ?? 0;
  const monthlyAdd = fund?.monthly_addition ?? 0;

  return (
    <div className="card-pad flex flex-col gap-4">
      <p className="text-small font-medium text-ink">Dip fund capital</p>

      {/* KPI pair */}
      <div className="grid grid-cols-2 gap-3">
        <div className="kpi-card pos-soft">
          <p className="text-caption font-medium uppercase tracking-wide text-ink-muted">
            Available
          </p>
          <p className="mono mt-1 text-[22px] font-semibold text-emerald">
            {inrFmt(balance)}
          </p>
        </div>
        <div className="kpi-card">
          <p className="text-caption font-medium uppercase tracking-wide text-ink-muted">
            Monthly addition
          </p>
          <p className="mono mt-1 text-[22px] font-semibold text-ink">
            {inrFmt(monthlyAdd)}
          </p>
        </div>
      </div>

      {/* Deployment ladder */}
      <div>
        <p className="mb-2 text-caption font-medium uppercase tracking-wide text-ink-muted">
          Deployment ladder
        </p>
        <div className="flex flex-col gap-2">
          {ladder.map((pct, i) => {
            const amount = (balance * pct) / 100;
            return (
              <div key={i} className="flex items-center gap-2">
                <span className="w-14 shrink-0 text-caption text-ink-muted">Signal {i + 1}</span>
                <div className="ladder-bar flex-1">
                  <div className="ladder-bar-fill" style={{ width: `${pct}%` }} />
                </div>
                <span className="mono w-8 shrink-0 text-right text-caption text-ink-secondary">
                  {pct}%
                </span>
                <span className="mono w-24 shrink-0 text-right text-caption text-ink-muted">
                  {inrFmt(amount)}
                </span>
              </div>
            );
          })}
        </div>
        <p className="mt-2 text-caption text-ink-faint">
          Total max 100% across 5 deepening signals.
        </p>
      </div>

      {/* Actions */}
      {showAdd ? (
        <div className="flex items-center gap-2 border-t border-line pt-3">
          <input
            type="number"
            min="1"
            placeholder="₹ amount"
            value={addAmount}
            onChange={(e) => setAddAmount(e.target.value)}
            className="mono flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-small text-ink outline-none focus:border-royal"
            aria-label="Amount to add to dip fund"
          />
          <button
            type="button"
            onClick={handleAdd}
            disabled={addCash.isPending}
            className="rounded-lg bg-royal px-4 py-2 text-small font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {addCash.isPending ? 'Adding…' : 'Add'}
          </button>
          <button
            type="button"
            onClick={() => setShowAdd(false)}
            className="rounded-lg border border-line px-4 py-2 text-small text-ink-secondary hover:bg-surface-2"
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="flex gap-2 border-t border-line pt-3">
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="rounded-lg border border-line px-3 py-1.5 text-small text-ink-secondary hover:bg-surface-2 transition-colors"
          >
            Add cash manually
          </button>
        </div>
      )}
    </div>
  );
}

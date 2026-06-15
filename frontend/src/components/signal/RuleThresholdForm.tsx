'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { useSignalRules, useSaveSignalRules } from '@/features/signal/api';
import type { SignalRules } from '@/features/signal/types';

const DEFAULTS: SignalRules = {
  nifty_threshold: -8,
  vix_threshold: 19,
  breadth_threshold: 0.8,
  deploy_ladder: [20, 20, 20, 20, 20],
  alerts_on: true,
};

function SliderRow({
  label,
  description,
  value,
  min,
  max,
  step,
  format,
  weight,
  onChange,
}: {
  label: string;
  description: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  weight: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex flex-col gap-2 border-b border-line py-4 last:border-0">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-caption font-medium uppercase tracking-wide text-ink-muted">{label}</p>
          <p className="mt-0.5 text-caption text-ink-secondary">{description}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="mono text-[22px] font-semibold text-ink">{format(value)}</span>
          <span className="badge-neutral">{weight}</span>
        </div>
      </div>
      <input
        type="range"
        className="slider"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={`${label} threshold`}
      />
      <div className="flex justify-between text-caption text-ink-faint">
        <span>{format(min)}</span>
        <span>{format(max)}</span>
      </div>
    </div>
  );
}

function AlertsToggle({
  on,
  onChange,
}: {
  on: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className={cn(
        'relative inline-flex h-5 w-9 cursor-pointer rounded-full border-2 border-transparent transition-colors',
        on ? 'bg-emerald' : 'bg-line',
      )}
    >
      <span
        className={cn(
          'pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform',
          on ? 'translate-x-4' : 'translate-x-0',
        )}
      />
      <span className="sr-only">{on ? 'Disable' : 'Enable'} daily alerts</span>
    </button>
  );
}

export function RuleThresholdForm() {
  const { data: savedRules, isLoading } = useSignalRules();
  const save = useSaveSignalRules();

  const [local, setLocal] = React.useState<SignalRules>(DEFAULTS);
  const [dirty, setDirty] = React.useState(false);

  // Sync server → local on first load
  React.useEffect(() => {
    if (savedRules) {
      setLocal(savedRules);
      setDirty(false);
    }
  }, [savedRules]);

  function update(patch: Partial<SignalRules>) {
    setLocal((prev) => ({ ...prev, ...patch }));
    setDirty(true);
  }

  async function handleSave() {
    await save.mutateAsync(local);
    setDirty(false);
  }

  function handleReset() {
    setLocal(DEFAULTS);
    setDirty(true);
  }

  if (isLoading) {
    return (
      <div className="card-pad animate-pulse space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded bg-surface-2" />
        ))}
      </div>
    );
  }

  return (
    <div className="card-pad">
      <p className="text-small font-medium text-ink">Signal thresholds</p>
      <p className="mt-0.5 text-caption text-ink-muted">
        Conditions that define your personal signal rules.
      </p>

      {/* Sliders */}
      <div className="mt-3">
        <SliderRow
          label="Nifty 50"
          description="Day decline % that counts as a dip"
          value={local.nifty_threshold}
          min={-20}
          max={0}
          step={0.5}
          format={(v) => `${v}%`}
          weight="20% weight"
          onChange={(v) => update({ nifty_threshold: v })}
        />
        <SliderRow
          label="India VIX"
          description="Fear index level to trigger Watch / Triggered"
          value={local.vix_threshold}
          min={12}
          max={35}
          step={0.5}
          format={(v) => v.toFixed(1)}
          weight="40% weight"
          onChange={(v) => update({ vix_threshold: v })}
        />
        <SliderRow
          label="Market breadth"
          description="Advance/Decline ratio lower bound"
          value={local.breadth_threshold}
          min={0.3}
          max={1.5}
          step={0.05}
          format={(v) => `A/D ${v.toFixed(2)}`}
          weight="40% weight"
          onChange={(v) => update({ breadth_threshold: v })}
        />
      </div>

      {/* Footer actions */}
      <div className="mt-4 flex items-center gap-3 border-t border-line pt-3">
        <button
          type="button"
          disabled={!dirty || save.isPending}
          onClick={handleSave}
          className={cn(
            'rounded-lg px-4 py-2 text-small font-medium transition-opacity',
            dirty && !save.isPending
              ? 'bg-royal text-white hover:opacity-90'
              : 'cursor-not-allowed bg-surface-2 text-ink-muted',
          )}
        >
          {save.isPending ? 'Saving…' : 'Save rules'}
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="rounded-lg border border-line px-4 py-2 text-small font-medium text-ink-secondary hover:bg-surface-2 transition-colors"
        >
          Reset to defaults
        </button>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-caption text-ink-muted">Daily alerts</span>
          <AlertsToggle
            on={local.alerts_on}
            onChange={(v) => update({ alerts_on: v })}
          />
        </div>
      </div>

      {save.isError && (
        <p className="mt-2 text-caption text-red">Failed to save. Please try again.</p>
      )}
    </div>
  );
}

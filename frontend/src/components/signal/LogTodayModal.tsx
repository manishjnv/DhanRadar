'use client';

import * as React from 'react';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useAddJournal } from '@/features/signal/api';
import { useVIX, useBreadth } from '@/features/signal/api';
import { useMarketIndices } from '@/hooks/useMarketIndices';
import type { JournalDecision, JournalEmotion } from '@/features/signal/types';

const DECISIONS: { value: JournalDecision; label: string }[] = [
  { value: 'deployed', label: 'Deployed' },
  { value: 'watched', label: 'Watched' },
  { value: 'skipped', label: 'Skipped' },
];

const EMOTIONS: { value: JournalEmotion; label: string }[] = [
  { value: 'fearful', label: 'Fearful' },
  { value: 'calm', label: 'Calm' },
  { value: 'excited', label: 'Excited' },
  { value: 'fomo', label: 'FOMO' },
  { value: 'disciplined', label: 'Disciplined' },
];

// Shared field / label classes — token-only, mirrors the Rules form inputs.
const FIELD_CLS =
  'mono rounded-md border border-line bg-surface-2 px-2.5 py-2 text-small text-ink focus:border-royal focus:outline-none';
const LABEL_CLS =
  'text-caption font-medium uppercase tracking-wide text-ink-muted';

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

interface LogTodayModalProps {
  onClose: () => void;
}

export function LogTodayModal({ onClose }: LogTodayModalProps) {
  const addJournal = useAddJournal();
  const { data: indices } = useMarketIndices();
  const { data: vix } = useVIX();
  const { data: breadth } = useBreadth();

  const nifty50 = indices?.find((i) => i.name === 'Nifty 50');

  const [date, setDate] = React.useState(todayISO);
  const [decision, setDecision] = React.useState<JournalDecision>('watched');
  const [amount, setAmount] = React.useState('');
  const [emotions, setEmotions] = React.useState<Set<JournalEmotion>>(new Set());
  const [notes, setNotes] = React.useState('');
  const [niftyPct, setNiftyPct] = React.useState(() =>
    nifty50?.change_pct != null ? String(nifty50.change_pct.toFixed(2)) : ''
  );
  const [vixLevel, setVixLevel] = React.useState(() =>
    vix?.value != null ? String(vix.value.toFixed(2)) : ''
  );
  const [breadthRatio, setBreadthRatio] = React.useState(() =>
    breadth?.ad_ratio != null ? String(breadth.ad_ratio.toFixed(3)) : ''
  );

  // Auto-fill market snapshot once when data first arrives; refs prevent re-fill on re-renders
  const niftyFilled = React.useRef(false);
  const vixFilled = React.useRef(false);
  const breadthFilled = React.useRef(false);

  React.useEffect(() => {
    if (!niftyFilled.current && nifty50?.change_pct != null) {
      niftyFilled.current = true;
      setNiftyPct(nifty50.change_pct.toFixed(2));
    }
  }, [nifty50?.change_pct]);

  React.useEffect(() => {
    if (!vixFilled.current && vix?.value != null) {
      vixFilled.current = true;
      setVixLevel(vix.value.toFixed(2));
    }
  }, [vix?.value]);

  React.useEffect(() => {
    if (!breadthFilled.current && breadth?.ad_ratio != null) {
      breadthFilled.current = true;
      setBreadthRatio(breadth.ad_ratio.toFixed(3));
    }
  }, [breadth?.ad_ratio]);

  function toggleEmotion(em: JournalEmotion) {
    setEmotions((prev) => {
      const next = new Set(prev);
      if (next.has(em)) next.delete(em);
      else next.add(em);
      return next;
    });
  }

  // Close on ESC
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await addJournal.mutateAsync({
      date,
      decision,
      amount_deployed: decision === 'deployed' && amount ? Number(amount) : null,
      emotions: Array.from(emotions),
      notes: notes.trim() || null,
      nifty_pct: niftyPct ? Number(niftyPct) : null,
      vix_level: vixLevel ? Number(vixLevel) : null,
      breadth_ratio: breadthRatio ? Number(breadthRatio) : null,
    });
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50"
      role="dialog"
      aria-modal="true"
      aria-label="Log today's decision"
    >
      {/* Backdrop — button so a11y click/keyboard rules are satisfied */}
      <button
        type="button"
        className="absolute inset-0 h-full w-full cursor-default border-0 bg-black/50"
        onClick={onClose}
        aria-label="Close dialog"
        tabIndex={-1}
      />
      {/* Panel — above backdrop */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="card card-pad mx-4 flex w-full max-w-md flex-col gap-4 pointer-events-auto max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="flex items-center justify-between">
            <p className="text-body font-semibold text-ink">
              Log today&apos;s decision
            </p>
            <button
              type="button"
              onClick={onClose}
              className="leading-none text-ink-muted hover:text-ink"
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Date */}
            <label className="flex flex-col gap-1">
              <span className={LABEL_CLS}>Date</span>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
                className={FIELD_CLS}
              />
            </label>

            {/* Decision */}
            <div className="flex flex-col gap-1">
              <span className={LABEL_CLS}>Decision</span>
              <div className="flex gap-2">
                {DECISIONS.map(({ value, label }) => (
                  <Button
                    key={value}
                    type="button"
                    size="sm"
                    variant={decision === value ? 'primary' : 'outline'}
                    className="flex-1"
                    onClick={() => setDecision(value)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Amount deployed (only when deployed) */}
            {decision === 'deployed' && (
              <label className="flex flex-col gap-1">
                <span className={LABEL_CLS}>Amount deployed (₹)</span>
                <input
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  min={0}
                  placeholder="0"
                  className={FIELD_CLS}
                />
              </label>
            )}

            {/* How did you feel? — SEBI: personal reflection, not performance judgement */}
            <div className="flex flex-col gap-1">
              <span className={LABEL_CLS}>How did you feel?</span>
              <div className="flex flex-wrap gap-2">
                {EMOTIONS.map(({ value, label }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => toggleEmotion(value)}
                    className={`chip${emotions.has(value) ? ' active' : ''}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Notes */}
            <label className="flex flex-col gap-1">
              <span className={LABEL_CLS}>Notes (optional)</span>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="What were you thinking?"
                className="resize-y rounded-md border border-line bg-surface-2 px-2.5 py-2 text-small text-ink focus:border-royal focus:outline-none"
              />
            </label>

            {/* Market snapshot (auto-filled, user-editable) */}
            <div className="flex flex-col gap-1">
              <span className={LABEL_CLS}>Market snapshot (auto-filled)</span>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: 'Nifty %', value: niftyPct, set: setNiftyPct, placeholder: '0.00' },
                  { label: 'VIX', value: vixLevel, set: setVixLevel, placeholder: '0.00' },
                  { label: 'A/D', value: breadthRatio, set: setBreadthRatio, placeholder: '0.000' },
                ].map(({ label, value, set, placeholder }) => (
                  <label key={label} className="flex flex-col gap-1">
                    <span className="text-caption text-ink-faint">{label}</span>
                    <input
                      type="number"
                      step="any"
                      value={value}
                      onChange={(e) => set(e.target.value)}
                      placeholder={placeholder}
                      className="mono rounded-md border border-line bg-surface-2 px-2 py-1.5 text-small text-ink focus:border-royal focus:outline-none"
                    />
                  </label>
                ))}
              </div>
            </div>

            {/* Submit */}
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={addJournal.isPending}
            >
              {addJournal.isPending ? 'Saving…' : 'Save entry'}
            </Button>

            {addJournal.isError && (
              <p className="text-caption text-red">
                Failed to save. Please try again.
              </p>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}

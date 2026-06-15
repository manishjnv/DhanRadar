'use client';

import * as React from 'react';
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
        className="absolute inset-0 w-full h-full"
        style={{ background: 'rgba(0,0,0,0.5)', cursor: 'default', border: 'none' }}
        onClick={onClose}
        aria-label="Close dialog"
        tabIndex={-1}
      />
      {/* Panel — above backdrop */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      <div
        className="card card-pad w-full max-w-md mx-4 flex flex-col gap-4 pointer-events-auto"
        style={{ maxHeight: '90vh', overflowY: 'auto' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)' }}>
            Log today&apos;s decision
          </p>
          <button
            type="button"
            onClick={onClose}
            style={{ fontSize: 18, color: 'var(--text-muted)', lineHeight: 1 }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Date */}
          <label className="flex flex-col gap-1">
            <span style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
              Date
            </span>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--surface-2)',
                color: 'var(--text)',
                fontSize: 13,
                fontFamily: 'var(--dr-font-mono)',
              }}
            />
          </label>

          {/* Decision */}
          <div className="flex flex-col gap-1">
            <span style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
              Decision
            </span>
            <div className="flex gap-2">
              {DECISIONS.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setDecision(value)}
                  className={decision === value ? 'btn btn-accent' : 'btn btn-outline'}
                  style={{ flex: 1, fontSize: 13 }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Amount deployed (only when deployed) */}
          {decision === 'deployed' && (
            <label className="flex flex-col gap-1">
              <span style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
                Amount deployed (₹)
              </span>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                min={0}
                placeholder="0"
                style={{
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--surface-2)',
                  color: 'var(--text)',
                  fontSize: 13,
                  fontFamily: 'var(--dr-font-mono)',
                }}
              />
            </label>
          )}

          {/* How did you feel? — SEBI: personal reflection, not performance judgement */}
          <div className="flex flex-col gap-1">
            <span style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
              How did you feel?
            </span>
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
            <span style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
              Notes (optional)
            </span>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="What were you thinking?"
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--surface-2)',
                color: 'var(--text)',
                fontSize: 13,
                resize: 'vertical',
              }}
            />
          </label>

          {/* Market snapshot (auto-filled, user-editable) */}
          <div className="flex flex-col gap-1">
            <span style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
              Market snapshot (auto-filled)
            </span>
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: 'Nifty %', value: niftyPct, set: setNiftyPct, placeholder: '0.00' },
                { label: 'VIX', value: vixLevel, set: setVixLevel, placeholder: '0.00' },
                { label: 'A/D', value: breadthRatio, set: setBreadthRatio, placeholder: '0.000' },
              ].map(({ label, value, set, placeholder }) => (
                <label key={label} className="flex flex-col gap-1">
                  <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>{label}</span>
                  <input
                    type="number"
                    step="any"
                    value={value}
                    onChange={(e) => set(e.target.value)}
                    placeholder={placeholder}
                    style={{
                      padding: '6px 8px',
                      borderRadius: 6,
                      border: '1px solid var(--border)',
                      background: 'var(--surface-2)',
                      color: 'var(--text)',
                      fontSize: 12,
                      fontFamily: 'var(--dr-font-mono)',
                    }}
                  />
                </label>
              ))}
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            className="btn btn-accent"
            disabled={addJournal.isPending}
          >
            {addJournal.isPending ? 'Saving…' : 'Save entry'}
          </button>

          {addJournal.isError && (
            <p style={{ fontSize: 12, color: 'var(--dr-red)' }}>
              Failed to save. Please try again.
            </p>
          )}
        </form>
      </div>
      </div>
    </div>
  );
}

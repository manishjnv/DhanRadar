/**
 * WhyThisLabelPanel — F1-A "Why this label" explainability surface.
 *
 * Renders, for a single fund, the backend-supplied `contributing_signals` /
 * `contradicting_signals` — the deterministic, compliance-approved factual
 * phrases from the scoring engine's signal vocabulary — VERBATIM. This is the
 * educational "why" beneath each non-advisory label, and DhanRadar's core
 * differentiation versus competitors that ship a bare label or star.
 *
 * Compliance invariants (non-neg #1, #2, #9):
 *   - NO numeric score / factor weights / raw confidence float in the DOM.
 *     Signals are factual text; this component adds NO numbers of its own.
 *   - Advisory-verb ban: signals are rendered VERBATIM from the backend; the
 *     component adds NO advisory copy (no buy/sell/hold/switch/keep/pause/exit).
 *   - Empty-state honesty (BLOCKERS B71): when BOTH lists are empty the panel
 *     does NOT imply a clean bill — it states the fund could not be benchmarked
 *     against category peers yet. `on_track` with no signals must never read as
 *     reassurance.
 *   - The page-level <DisclosureBundle/> already covers this labelled-holdings
 *     surface (non-neg #9); this inline sub-panel does not duplicate it.
 *
 * Design tokens: Geist/warm from tokens.css (--surface-2, --border, --text*,
 * --dr-emerald, --dr-amber). No ad-hoc colours, no Tailwind arbitrary values.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';
import { FactorStrengthBar } from './FactorStrengthBar';
import { LabelHistoryChart } from '@/components/mf/LabelHistoryChart';
import type { LabelHistoryEntry } from '@/features/mf/types';

export interface WhyThisLabelPanelProps {
  /** Verbatim factual phrases that support the fund's label. */
  contributingSignals: string[];
  /** Verbatim factual phrases that point against the fund's label. */
  contradictingSignals: string[];
  /** Feature 4: named confidence quality bands — "high"/"medium"/"low" only, never floats.
   *  null/absent on old cached reports; renders nothing when missing. */
  confidenceFactors?: Record<string, 'high' | 'medium' | 'low'> | null;
  /** Feature 2: label history entries for this fund for the timeline chart. */
  historyEntries?: LabelHistoryEntry[];
  /** Feature 2: true when the history endpoint returned 402 (Plus gate). */
  historyLocked?: boolean;
  /** Optional DOM id so a toggle button can aria-control this panel. */
  id?: string;
}

/** Render a string[] as a bulleted, non-advisory list. Verbatim — no added copy. */
function SignalList({
  testid,
  signals,
  accent,
}: {
  testid: string;
  signals: string[];
  accent: string;
}) {
  return (
    <ul
      data-testid={testid}
      className="mt-1 p-0 list-none flex flex-col gap-1"
    >
      {signals.map((s, i) => (
        <li
          key={i}
          className="font-sans text-caption text-ink-secondary pl-3.5 relative"
        >
          <span className={cn('absolute left-0', accent)} aria-hidden="true">
            ·
          </span>
          {s}
        </li>
      ))}
    </ul>
  );
}

export function WhyThisLabelPanel({
  contributingSignals,
  contradictingSignals,
  confidenceFactors,
  historyEntries,
  historyLocked,
  id,
}: WhyThisLabelPanelProps) {
  const hasContributing = contributingSignals.length > 0;
  const hasContradicting = contradictingSignals.length > 0;
  const noSignals = !hasContributing && !hasContradicting;
  const hasFactors =
    confidenceFactors != null && Object.keys(confidenceFactors).length > 0;

  return (
    <div
      id={id}
      data-testid="why-this-label"
      className="font-sans bg-surface-2 border border-line rounded-lg p-3"
    >
      <p
        className="mb-2 text-caption font-bold tracking-widest uppercase text-ink-muted"
      >
        Why this label
      </p>

      {hasFactors && (
        <div className="mb-3">
          <FactorStrengthBar factors={confidenceFactors!} />
        </div>
      )}

      {noSignals ? (
        <p
          data-testid="why-empty"
          className="text-caption text-ink-muted leading-relaxed"
        >
          We couldn&apos;t benchmark this fund against its category peers yet, so there
          are no signals to show. This is a data gap, not a clean bill of health.
        </p>
      ) : (
        <div className="flex flex-col gap-2.5">
          <div>
            <p className="text-caption font-semibold text-ink">
              Factors consistent with this label
            </p>
            {hasContributing ? (
              <SignalList
                testid="why-contributing"
                signals={contributingSignals}
                accent="text-emerald"
              />
            ) : (
              <p
                data-testid="why-contributing-empty"
                className="mt-0.5 text-caption text-ink-muted"
              >
                None recorded.
              </p>
            )}
          </div>
          <div>
            <p className="text-caption font-semibold text-ink">
              Factors that may weigh against it
            </p>
            {hasContradicting ? (
              <SignalList
                testid="why-contradicting"
                signals={contradictingSignals}
                accent="text-amber"
              />
            ) : (
              <p
                data-testid="why-contradicting-empty"
                className="mt-0.5 text-caption text-ink-muted"
              >
                None recorded.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Feature 2: label history timeline. Renders even when history is empty
          (shows "not enough history yet"); Plus-gated with blur overlay. Only
          mount when the prop is present so old call sites without history don't
          fire a useless 402 attempt. */}
      {historyEntries !== undefined && (
        <LabelHistoryChart
          history={historyEntries}
          isLocked={!!historyLocked}
        />
      )}
    </div>
  );
}

'use client';

/**
 * ResearchAssistant — F2 AI research assistant for Plus users.
 *
 * Lets users ask educational questions grounded in their own portfolio data.
 * Non-advisory: never contains buy/sell/hold/switch/exit/avoid/rebalance verbs.
 * Gating: Plus-only (402 → upgrade prompt); 10 questions/day (daily_cap state).
 * Compliance invariants (non-neg #1, #2, #9):
 *   - All advisory-verb checking happens on the backend (QualityValidator).
 *   - No numeric scores/factors/weights rendered here.
 *   - NOT_ADVICE disclaimer shown inline with every answer (non-neg #9).
 *   - refusal_triggered answers are reframed as educational boundaries.
 */

import * as React from 'react';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { useResearchAsk } from '@/features/mf/api';
import type { ResearchAskResponse } from '@/features/mf/types';
import { ApiError } from '@/lib/apiClient';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const NOT_ADVICE = 'For education only — not investment advice.';

function CitationsList({ citations }: { citations: string[] }) {
  const [open, setOpen] = React.useState(false);
  if (citations.length === 0) return null;
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-caption text-ink-muted underline underline-offset-2 hover:text-ink focus-visible:outline-none"
      >
        {open ? 'Hide' : 'Show'} {citations.length} citation{citations.length !== 1 ? 's' : ''}
      </button>
      <div
        className={cn(
          'grid transition-all duration-200',
          open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}
      >
        <div className="overflow-hidden">
          <ul className="mt-2 flex flex-col gap-1 pl-3 border-l-2 border-line">
            {citations.map((c, i) => (
              <li key={i} className="text-caption text-ink-secondary">
                {c}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

interface QAPair {
  question: string;
  response: ResearchAskResponse;
}

function AnswerBlock({ qa }: { qa: QAPair }) {
  const { response: r } = qa;
  return (
    <div className="flex flex-col gap-2 py-3 border-b border-line last:border-0">
      <p className="text-small font-medium text-ink-muted">{qa.question}</p>

      {r.state === 'ok' ? (
        <div className="flex flex-col gap-1.5">
          {r.refusal_triggered && (
            <p className="text-caption font-medium text-amber">
              Educational boundary: this question touches personal investment decisions,
              which are yours to make with a qualified advisor.
            </p>
          )}
          <p className="text-small text-ink whitespace-pre-line leading-relaxed">
            {r.answer}
          </p>
          {r.citations && r.citations.length > 0 && (
            <CitationsList citations={r.citations} />
          )}
          <p className="text-caption text-ink-muted italic mt-1">
            {r.disclaimer ?? NOT_ADVICE}
          </p>
        </div>
      ) : r.state === 'insufficient_data' ? (
        <p className="text-small text-ink-secondary">
          Not enough data in your portfolio to answer this question reliably.
        </p>
      ) : r.state === 'daily_cap' ? (
        <p className="text-small text-ink-secondary">
          Daily question limit reached (10 per day). Try again tomorrow.
        </p>
      ) : (
        <p className="text-small text-ink-secondary">
          {r.reason === 'consent_required'
            ? 'Please grant cross-border AI consent in your account settings to use this feature.'
            : 'This question could not be answered right now. Please try again later.'}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Upgrade gate (shown when 402 is returned)
// ---------------------------------------------------------------------------

function UpgradePrompt() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Portfolio Research Assistant</CardTitle>
      </CardHeader>
      <CardBody>
        <div className="flex flex-col items-center gap-3 py-6 text-center">
          <p className="text-small text-ink-secondary max-w-sm">
            Ask educational questions about your own portfolio data — category
            concentration, label distribution, and more.
          </p>
          <p className="text-small font-medium text-ink">
            Available on DhanRadar Plus
          </p>
          <a
            href="/account/upgrade"
            className="mt-1 inline-flex h-9 items-center rounded-full bg-navy px-5 text-small font-medium text-white hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
          >
            Upgrade to Plus &rarr;
          </a>
        </div>
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export interface ResearchAssistantProps {
  jobId: string;
}

export function ResearchAssistant({ jobId }: ResearchAssistantProps) {
  const [question, setQuestion] = React.useState('');
  const [history, setHistory] = React.useState<QAPair[]>([]);
  const [isUpgradeLocked, setIsUpgradeLocked] = React.useState(false);
  const historyEndRef = React.useRef<HTMLDivElement>(null);

  const { mutate, isPending } = useResearchAsk(jobId);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || isPending) return;

    mutate(q, {
      onSuccess: (data) => {
        setHistory((h) => [...h, { question: q, response: data }]);
        setQuestion('');
        setTimeout(
          () =>
            historyEndRef.current?.scrollIntoView({
              behavior: 'smooth',
              block: 'nearest',
            }),
          50,
        );
      },
      onError: (err) => {
        if (err instanceof ApiError && err.problem.status === 402) {
          setIsUpgradeLocked(true);
          return;
        }
        setHistory((h) => [
          ...h,
          { question: q, response: { state: 'unavailable', reason: 'error' } },
        ]);
        setQuestion('');
      },
    });
  };

  if (isUpgradeLocked) return <UpgradePrompt />;

  const remaining = 500 - question.length;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Portfolio Research Assistant</CardTitle>
      </CardHeader>
      <CardBody>
        <p className="text-caption text-ink-muted mb-4">
          Ask educational questions about your portfolio. Answers are grounded in your
          own holdings data.
        </p>

        {history.length > 0 && (
          <div
            className="mb-4 flex flex-col"
            aria-live="polite"
            aria-label="Research question history"
          >
            {history.map((qa, i) => (
              <AnswerBlock key={i} qa={qa} />
            ))}
            <div ref={historyEndRef} />
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          <div className="relative">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value.slice(0, 500))}
              placeholder="e.g. What is my largest category exposure?"
              rows={3}
              maxLength={500}
              disabled={isPending}
              aria-label="Research question"
              className="w-full resize-none rounded-lg border border-line bg-surface-2 p-3 pr-10 text-small text-ink placeholder:text-ink-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:opacity-60"
            />
            <span
              className={cn(
                'absolute bottom-2 right-3 text-caption tabular-nums select-none',
                remaining < 50 ? 'text-amber' : 'text-ink-muted',
              )}
            >
              {remaining}
            </span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-caption text-ink-muted italic">
              {NOT_ADVICE} · Plus · 10 questions/day
            </p>
            <button
              type="submit"
              disabled={isPending || !question.trim()}
              className="shrink-0 h-8 px-4 rounded-full bg-navy text-small text-white font-medium hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:opacity-40 transition-opacity"
            >
              {isPending ? 'Asking…' : 'Ask'}
            </button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

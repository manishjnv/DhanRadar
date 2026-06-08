'use client';

/**
 * RiskQuiz — presentational multi-question risk-profiling form.
 *
 * Compliance rules:
 *  - No advisory verbs (no buy/sell/hold/caution/avoid) anywhere in copy.
 *  - No numeric scores, factor weights, or fair-values in the DOM.
 *  - Resulting risk_profile is surfaced as a word label only.
 *
 * Accessibility contract:
 *  - Each question is a <fieldset> with a <legend> — radio group a11y.
 *  - Each option is a <label> wrapping a <input type="radio">.
 *  - Submit is disabled until all 5 questions have a selection.
 *  - focus-visible rings on all interactive elements.
 *  - Error surfaced via ErrorCard; loading via disabled button + text swap.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';
import { Button } from '@/components/ui/Button';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { QUIZ_QUESTIONS } from './questions';
import { useSubmitRiskQuiz } from './api';
import { ApiError } from '@/lib/apiClient';

export interface RiskQuizProps {
  onComplete: () => void;
}

export function RiskQuiz({ onComplete }: RiskQuizProps) {
  // answers[i] is the selected option index (0..3) for question i, or null
  const [answers, setAnswers] = React.useState<(number | null)[]>(
    () => Array(QUIZ_QUESTIONS.length).fill(null),
  );

  const mutation = useSubmitRiskQuiz();

  const allAnswered = answers.every((a) => a !== null);

  function handleSelect(questionIdx: number, optionIdx: number) {
    setAnswers((prev) => {
      const next = [...prev];
      next[questionIdx] = optionIdx;
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!allAnswered || mutation.isPending) return;

    mutation.mutate(
      { answers: answers as number[] },
      { onSuccess: () => onComplete() },
    );
  }

  // Derive a human-readable error message without exposing internals
  function errorMessage(): string {
    const err = mutation.error;
    if (err instanceof ApiError) {
      return err.problem.detail ?? err.problem.title ?? 'Something went wrong. Please try again.';
    }
    return 'Something went wrong. Please try again.';
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      aria-label="Risk profile questionnaire"
      className="flex flex-col gap-8"
    >
      {QUIZ_QUESTIONS.map((question, qIdx) => (
        <fieldset key={question.id} className="flex flex-col gap-3">
          <legend className="text-body font-medium text-ink">
            <span className="mr-2 text-ink-secondary" aria-hidden="true">
              {qIdx + 1}.
            </span>
            {question.prompt}
          </legend>

          <div className="flex flex-col gap-2">
            {question.options.map((option, oIdx) => {
              const inputId = `${question.id}_opt${oIdx}`;
              const isSelected = answers[qIdx] === oIdx;
              return (
                <label
                  key={oIdx}
                  htmlFor={inputId}
                  className={cn(
                    'flex cursor-pointer items-start gap-3 rounded-lg border px-4 py-3 transition-colors',
                    isSelected
                      ? 'border-royal bg-royal/5 text-ink'
                      : 'border-line bg-surface text-ink hover:bg-surface-2',
                  )}
                >
                  <input
                    id={inputId}
                    type="radio"
                    name={question.id}
                    value={oIdx}
                    checked={isSelected}
                    onChange={() => handleSelect(qIdx, oIdx)}
                    className={cn(
                      'mt-0.5 h-4 w-4 shrink-0',
                      'accent-royal',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                    )}
                  />
                  <span className="text-small leading-snug">{option}</span>
                </label>
              );
            })}
          </div>
        </fieldset>
      ))}

      {/* Error state */}
      {mutation.isError && (
        <ErrorCard
          title="Could not save your profile"
          message={errorMessage()}
          onRetry={() => mutation.reset()}
        />
      )}

      {/* Submit */}
      <div className="flex justify-end">
        <Button
          type="submit"
          variant="primary"
          size="md"
          disabled={!allAnswered || mutation.isPending}
          aria-disabled={!allAnswered || mutation.isPending}
        >
          {mutation.isPending ? 'Saving…' : 'Set my risk profile'}
        </Button>
      </div>
    </form>
  );
}

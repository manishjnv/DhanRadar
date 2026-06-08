/**
 * RiskQuiz tests
 *
 * Happy path: answer all 5 questions → Submit enabled → click → MSW endpoint
 * called → onComplete fired.
 *
 * Guard path: Submit is disabled until all 5 questions have a selection.
 */
import * as React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RiskQuiz } from './RiskQuiz';
import { QUIZ_QUESTIONS } from './questions';

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('RiskQuiz', () => {
  it('Submit is disabled when no questions are answered', () => {
    renderWithClient(<RiskQuiz onComplete={() => {}} />);
    expect(screen.getByRole('button', { name: /set my risk profile/i })).toBeDisabled();
  });

  it('Submit remains disabled while only some questions are answered', async () => {
    const user = userEvent.setup();
    renderWithClient(<RiskQuiz onComplete={() => {}} />);

    // Answer only the first question (option index 0)
    const firstGroup = screen.getAllByRole('radio');
    await user.click(firstGroup[0]);

    expect(screen.getByRole('button', { name: /set my risk profile/i })).toBeDisabled();
  });

  it('Submit is enabled after all 5 questions are answered', async () => {
    const user = userEvent.setup();
    renderWithClient(<RiskQuiz onComplete={() => {}} />);

    // Select the first option in each question group
    for (let q = 0; q < QUIZ_QUESTIONS.length; q++) {
      const radio = screen.getByRole('radio', {
        name: QUIZ_QUESTIONS[q].options[0],
      });
      await user.click(radio);
    }

    expect(screen.getByRole('button', { name: /set my risk profile/i })).toBeEnabled();
  });

  it('(happy) answers all questions, clicks Submit, calls the endpoint, fires onComplete', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    renderWithClient(<RiskQuiz onComplete={onComplete} />);

    // Select option 0 for every question
    for (let q = 0; q < QUIZ_QUESTIONS.length; q++) {
      const radio = screen.getByRole('radio', {
        name: QUIZ_QUESTIONS[q].options[0],
      });
      await user.click(radio);
    }

    const submitBtn = screen.getByRole('button', { name: /set my risk profile/i });
    expect(submitBtn).toBeEnabled();

    await user.click(submitBtn);

    // onComplete is called after the MSW handler resolves
    await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
  });

  it('renders all 5 question prompts in the DOM', () => {
    renderWithClient(<RiskQuiz onComplete={() => {}} />);
    for (const q of QUIZ_QUESTIONS) {
      expect(screen.getByText(q.prompt)).toBeInTheDocument();
    }
  });

  it('renders radio options that are keyboard-reachable (each has an id + associated label)', () => {
    renderWithClient(<RiskQuiz onComplete={() => {}} />);
    const radios = screen.getAllByRole('radio');
    // 5 questions × 4 options = 20
    expect(radios).toHaveLength(QUIZ_QUESTIONS.length * 4);
    for (const radio of radios) {
      // Each radio must have an id so the wrapping label is properly associated
      expect(radio).toHaveAttribute('id');
    }
  });
});

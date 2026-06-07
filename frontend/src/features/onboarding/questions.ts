/**
 * Onboarding risk-quiz question bank.
 *
 * Five questions; each has four options ordered from most conservative
 * (index 0) to most growth-oriented (index 3).
 *
 * Compliance rules observed:
 *  - No advisory verbs (no buy/sell/hold/caution/avoid).
 *  - No numeric scores or percentages in copy.
 *  - Educational framing only (not a recommendation to act).
 */

export interface QuizQuestion {
  id: string;
  prompt: string;
  options: [string, string, string, string];
}

export const QUIZ_QUESTIONS: QuizQuestion[] = [
  {
    id: 'q1_goal',
    prompt: 'What is your primary financial goal for this investment?',
    options: [
      'Preserve the value of my money with minimal risk',
      'Earn a modest, steady return over time',
      'Grow my wealth meaningfully over several years',
      'Maximise long-term growth, accepting higher variability',
    ],
  },
  {
    id: 'q2_horizon',
    prompt: 'How long do you plan to keep this investment before needing the funds?',
    options: [
      'Less than 2 years',
      '2 to 4 years',
      '5 to 9 years',
      '10 years or more',
    ],
  },
  {
    id: 'q3_reaction',
    prompt:
      'If the value of your portfolio declined noticeably over a few months, what would you most likely do?',
    options: [
      'Move everything to a more stable option immediately',
      'Reduce my allocation to higher-risk funds',
      'Wait and review again after six months',
      'Continue as planned — short-term moves do not change my view',
    ],
  },
  {
    id: 'q4_income',
    prompt: 'How stable is the income or cash flow you rely on for living expenses?',
    options: [
      'Variable or uncertain — I need to be cautious',
      'Mostly stable, but with some uncertainty',
      'Stable with occasional variation',
      'Very stable and predictable',
    ],
  },
  {
    id: 'q5_experience',
    prompt: 'How would you describe your experience with equity or mutual fund investments?',
    options: [
      'I have no prior experience and prefer low complexity',
      'I have some experience but keep it simple',
      'I am comfortable with a diversified equity portfolio',
      'I actively follow markets and understand various fund categories',
    ],
  },
];

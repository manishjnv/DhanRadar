/**
 * MoodFactorGuide — educational "what moves the mood" explainer.
 *
 * Plain-language description of each signal the Market Mood considers and what a
 * high/low reading indicates about sentiment. Pure EDUCATION (our differentiator):
 * descriptive only — no advice, no numbers, no trading verbs. "fear"/"greed" are
 * the mood's own level words, not directions to act.
 */

const FACTORS: { name: string; what: string }[] = [
  {
    name: 'Nifty Trend',
    what: 'How the Nifty 50 moved today. A rising market usually reflects optimism (toward greed); a falling one reflects caution (toward fear).',
  },
  {
    name: 'Market Breadth',
    what: 'How many stocks rose versus fell. Broad gains across many stocks signal confidence; gains in only a few signal a narrow, nervous market.',
  },
  {
    name: 'India VIX',
    what: "The market's 'nervousness meter' — how big a swing traders expect ahead. Low VIX means calm and confident; high VIX means anxious.",
  },
  {
    name: 'FII Flows',
    what: 'How much money foreign investors put into or pulled out of the market today. Heavy inflows lift the mood; heavy outflows drag it down.',
  },
  {
    name: 'Global Indices',
    what: 'How major world markets (like the US S&P 500) moved. Strong global markets tend to lift Indian sentiment, and weak ones weigh on it.',
  },
  {
    name: 'DII Flows',
    what: 'How much money domestic institutions (mutual funds, insurers) put in or took out. Steady local inflows support the mood even when foreign investors pull money out.',
  },
  {
    name: 'US 10-Year Yield',
    what: 'The interest rate on US government bonds. When it is high, money tends to leave riskier markets like India (toward fear); lower is friendlier.',
  },
  {
    name: 'Brent Crude',
    what: 'The global oil price. India imports most of its oil, so expensive oil pressures the economy (toward fear); cheaper oil is a tailwind.',
  },
  {
    name: 'USD / INR',
    what: 'The rupee versus the dollar. A strengthening rupee signals inflows and confidence; a weakening rupee signals caution.',
  },
  {
    name: 'Put-Call Ratio',
    what: 'An options-market gauge of positioning, read in reverse: very high (lots of protection bought) often marks fear; very low marks greed.',
  },
  {
    name: 'News Sentiment',
    what: 'The overall tone of recent market-news headlines, read as positive, neutral, or negative.',
  },
];

export function MoodFactorGuide() {
  return (
    <section
      aria-label="What moves the market mood"
      className="rounded-lg border border-line bg-surface p-4 sm:p-5"
    >
      <p className="text-small font-medium text-ink">What moves the mood</p>
      <p className="mt-1 text-caption text-ink-muted">
        The mood is a blend of these market signals. Here&rsquo;s what each one is, in plain words —
        educational only, not a tip to act on.
      </p>
      <dl className="mt-4 grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
        {FACTORS.map((f) => (
          <div key={f.name}>
            <dt className="text-small font-medium text-ink">{f.name}</dt>
            <dd className="mt-0.5 text-small text-ink-secondary">{f.what}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

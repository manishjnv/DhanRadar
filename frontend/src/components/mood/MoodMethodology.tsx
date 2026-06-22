/**
 * MoodMethodology — plain-language "how the mood is calculated" explainer.
 *
 * Describes the METHOD (blend signals → score from fearful to greedy → bucket
 * into five levels → confidence from coverage) in everyday words. COMPLIANCE:
 * describes the approach only — NO numeric score, NO exact weights, NO advice.
 * Collapsed by default so it never crowds the read.
 */

export function MoodMethodology() {
  return (
    <details className="rounded-lg border border-line bg-surface px-4 py-3 [&_summary]:cursor-pointer">
      <summary className="text-small font-medium text-ink marker:text-ink-muted">
        How is this calculated?
      </summary>
      <div className="mt-3 space-y-3 text-small text-ink-secondary">
        <p>
          The Market Mood blends several market signals — like how the Nifty moved, how nervous the
          options market is, and whether money is flowing into or out of the market — into a single
          read.
        </p>
        <p>
          Each signal is rated on a scale from fearful to greedy. Those ratings are combined into one
          overall reading, with some signals (such as the broad market trend) counting a little more
          than others, and that reading is placed into one of five levels: Extreme Fear, Fear,
          Neutral, Greed, or Extreme Greed.
        </p>
        <p>
          The more signals that have fresh data, the more confident the read — when only a few are
          available we mark it lower-confidence and say so in words. It is a descriptive read of how
          the market feels today, not a prediction and not a tip to act on.
        </p>
      </div>
    </details>
  );
}

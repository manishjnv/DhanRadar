/**
 * MoodFactorGuide — educational SIGNAL CARDS ("what moves the mood").
 *
 * Each market signal as a card: icon + name + a static "bias" badge (its general
 * tendency) + a plain-English description + (when `signalState` is given) today's
 * live role — Supporting / Counterweight + strength, or "Awaiting data".
 *
 * COMPLIANCE: descriptive education only — no advice, no numbers, no trading
 * verbs; no count and no score (non-neg #2). "fear"/"greed" are the mood's level
 * words. Per-signal role/strength comes from the public contributing/contradicting
 * factors (labels match the backend), never a raw value.
 */

import {
  Activity,
  ArrowLeftRight,
  BarChart3,
  Building2,
  Droplet,
  Globe,
  IndianRupee,
  Landmark,
  Newspaper,
  Scale,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react';

interface Factor {
  name: string;
  Icon: LucideIcon;
  bias: string; // general tendency (educational, not today's value)
  what: string;
}

const FACTORS: Factor[] = [
  {
    name: 'Nifty Trend',
    Icon: TrendingUp,
    bias: 'Toward greed when rising',
    what: 'How the Nifty 50 moved today. A rising market usually reflects optimism (toward greed); a falling one reflects caution (toward fear).',
  },
  {
    name: 'Market Breadth',
    Icon: BarChart3,
    bias: 'Toward greed when broad',
    what: 'How many stocks rose versus fell. Broad gains across many stocks signal confidence; gains in only a few signal a narrow, nervous market.',
  },
  {
    name: 'India VIX',
    Icon: Activity,
    bias: 'Read in reverse',
    what: "The market's 'nervousness meter' — how big a swing traders expect ahead. Low VIX means calm and confident; high VIX means anxious.",
  },
  {
    name: 'FII Flows',
    Icon: ArrowLeftRight,
    bias: 'Toward greed on inflows',
    what: 'How much money foreign investors put into or pulled out of the market today. Heavy inflows lift the mood; heavy outflows drag it down.',
  },
  {
    name: 'Global Indices',
    Icon: Globe,
    bias: 'Toward greed when strong',
    what: 'How major world markets (like the US S&P 500) moved. Strong global markets tend to lift Indian sentiment, and weak ones weigh on it.',
  },
  {
    name: 'DII Flows',
    Icon: Building2,
    bias: 'Toward greed on inflows',
    what: 'How much money domestic institutions (mutual funds, insurers) put in or took out. Steady local inflows support the mood even when foreign investors pull money out.',
  },
  {
    name: 'US 10Y Yield',
    Icon: Landmark,
    bias: 'Toward fear when high',
    what: 'The interest rate on the US 10-year government bond. When it is high, money tends to leave riskier markets like India (toward fear); lower is friendlier.',
  },
  {
    name: 'Brent Crude',
    Icon: Droplet,
    bias: 'Toward fear when high',
    what: 'The global oil price. India imports most of its oil, so expensive oil pressures the economy (toward fear); cheaper oil is a tailwind.',
  },
  {
    name: 'USD/INR',
    Icon: IndianRupee,
    bias: 'Read in reverse',
    what: 'The rupee versus the dollar. A strengthening rupee signals inflows and confidence; a weakening rupee signals caution.',
  },
  {
    name: 'Put-Call Ratio',
    Icon: Scale,
    bias: 'Read in reverse',
    what: 'An options-market gauge of positioning, read in reverse: very high (lots of protection bought) often marks fear; very low marks greed.',
  },
  {
    name: 'News Sentiment',
    Icon: Newspaper,
    bias: 'Toward greed when positive',
    what: 'The overall tone of recent market-news headlines, read as positive, neutral, or negative.',
  },
];

const TIER_WORD: Record<string, string> = { strong: 'Strong', moderate: 'Moderate', slight: 'Slight' };

export interface SignalRole {
  side: 'supporting' | 'counterweight';
  tier: string;
}

export interface MoodFactorGuideProps {
  /** Today's live role per signal label (from contributing/contradicting factors).
   *  Optional — when present, each card shows Supporting/Counterweight + strength,
   *  or "Awaiting data". No count, no value (non-neg #2). */
  signalState?: ReadonlyMap<string, SignalRole>;
}

export function MoodFactorGuide({ signalState }: MoodFactorGuideProps) {
  const showState = signalState !== undefined;
  return (
    <section
      aria-label="What moves the market mood"
      className="rounded-lg border border-line bg-surface p-4 sm:p-5"
    >
      <p className="text-small font-medium text-ink">What moves the mood</p>
      <p className="mt-1 text-caption text-ink-muted">
        Each card is one market signal — what it is, in plain words
        {showState && ", and how it's pulling the mood today"}. Educational only, not a tip to act on.
      </p>

      <ul className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
        {FACTORS.map((f) => {
          const role = showState ? signalState!.get(f.name) : undefined;
          return (
            <li
              key={f.name}
              className="flex items-start gap-3 rounded-xl border border-line bg-surface-2/40 p-3.5"
            >
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-surface-3 text-ink-secondary">
                <f.Icon size={18} aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="text-small font-medium text-ink">{f.name}</span>
                  <span className="rounded-full bg-surface-3 px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-ink-muted">
                    {f.bias}
                  </span>
                </div>
                <p className="mt-1 text-small leading-snug text-ink-secondary">{f.what}</p>
                {showState && (
                  <p className="mt-1.5 text-caption font-medium">
                    {role ? (
                      <span className="text-ink-secondary">
                        {role.side === 'supporting' ? '+ Supporting' : '− Counterweight'} ·{' '}
                        {TIER_WORD[role.tier] ?? 'Slight'} today
                      </span>
                    ) : (
                      <span className="text-ink-faint">Awaiting data</span>
                    )}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

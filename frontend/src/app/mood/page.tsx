'use client';

/**
 * /mood — PUBLIC Market Mood (DMMI) page.
 *
 * Visual + colour match to the ui-system master mockup
 * (docs/ui-system/html/MMI Page.html) — founder rule 2026-06-22. Styling lives in
 * mmi.module.css (the reference palette, scoped). The mockup is numeric throughout;
 * here EVERY numeric slot is filled with a compliant word/label:
 *  #1  educational read only — no advisory verbs anywhere.
 *  #2  NO numeric score / 0-100 tick / factor value / count reaches the DOM. The
 *      gauge needle, driver-bar widths and confidence dots are visual positions
 *      derived from the regime/band, never a rendered number.
 *  #9  disclosure + not_advice from the API are rendered; standing Disclaimer via MaybeShell.
 */

import * as React from 'react';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { Compass } from 'lucide-react';
import {
  useMoodCurrent,
  useMoodHistory,
  useMacroQuotes,
  useMarketBreadth,
} from '@/features/mood/api';
import type { MacroQuote, MarketBreadth } from '@/features/mood/api';
import { ApiError } from '@/lib/apiClient';
import type { Regime, MoodFactor, MoodFactorTier } from '@/features/mood/types';
import { relativeTime } from '@/features/mood/relative-time';
import s from './mmi.module.css';

// ---------------------------------------------------------------------------
// Regime → display word, reference colour, gauge position (NO numbers in DOM —
// the position/colour are visual only).
// ---------------------------------------------------------------------------
const WORD: Record<Regime, string> = {
  extreme_fear: 'Extreme Fear',
  fear: 'Fear',
  neutral: 'Neutral',
  greed: 'Greed',
  extreme_greed: 'Extreme Greed',
  insufficient_data: 'Insufficient data',
  data_unavailable: 'Unavailable',
};
// Reference fear→greed colours (green = fear … red = greed), founder convention.
const HEX: Record<Regime, string> = {
  extreme_fear: '#10b981',
  fear: '#65a30d',
  neutral: '#d97706', // amber — matches the gauge's neutral (centre) zone, not black
  greed: '#f97316',
  extreme_greed: '#ef4444',
  insufficient_data: '#94a3b8',
  data_unavailable: '#94a3b8',
};
// Gauge needle fraction across the 180° arc (left = fear, right = greed).
const FRACTION: Record<Regime, number> = {
  extreme_fear: 0.08,
  fear: 0.29,
  neutral: 0.5,
  greed: 0.71,
  extreme_greed: 0.92,
  insufficient_data: 0.5,
  data_unavailable: 0.5,
};
// Scale-bar marker position (% along the gradient track).
const MARKER_PCT: Record<Regime, number> = {
  extreme_fear: 8,
  fear: 29,
  neutral: 50,
  greed: 71,
  extreme_greed: 92,
  insufficient_data: 50,
  data_unavailable: 50,
};

type Side = 'fear' | 'neu' | 'greed';
function side(r: Regime): Side {
  if (r === 'extreme_fear' || r === 'fear') return 'fear';
  if (r === 'greed' || r === 'extreme_greed') return 'greed';
  return 'neu';
}
function tlabelStyle(r: Regime): React.CSSProperties {
  const map: Record<Side, [string, string]> = {
    fear: ['rgba(16,185,129,.10)', '#10b981'],
    neu: ['rgba(245,158,11,.12)', '#f59e0b'],
    greed: ['rgba(239,68,68,.09)', '#ef4444'],
  };
  const [bg, color] = map[side(r)];
  return { background: bg, color };
}

// ---------------------------------------------------------------------------
// 180° gauge (ported from the mockup's gauge()). Decorative, aria-hidden, NO number.
// ---------------------------------------------------------------------------
function hex2rgb(h: string): [number, number, number] {
  return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
}
function lerp(a: string, b: string, f: number): string {
  const A = hex2rgb(a);
  const B = hex2rgb(b);
  return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * f)).join(',')})`;
}
const STOPS: [string, number][] = [
  ['#10b981', 0],
  ['#84cc16', 0.25],
  ['#f59e0b', 0.5],
  ['#f97316', 0.75],
  ['#ef4444', 1],
];
function Gauge({ regime, size = 240 }: { regime: Regime; size?: number }) {
  const scale = size / 190;
  const W = Math.round(190 * scale);
  const H = Math.round(112 * scale);
  const cx = 95 * scale;
  const cy = 98 * scale;
  const r = 76 * scale;
  const sw = 14 * scale;
  const a0 = Math.PI;
  const a1 = 2 * Math.PI;
  const steps = 60;
  const segs: React.ReactNode[] = [];
  for (let i = 0; i < steps; i++) {
    const t0 = i / steps;
    const t1 = (i + 1) / steps;
    const A0 = a0 + (a1 - a0) * t0;
    const A1 = a0 + (a1 - a0) * t1;
    const x0 = cx + r * Math.cos(A0);
    const y0 = cy + r * Math.sin(A0);
    const x1 = cx + r * Math.cos(A1);
    const y1 = cy + r * Math.sin(A1);
    let col = '#f59e0b';
    for (let k = 0; k < STOPS.length - 1; k++) {
      if (t0 >= STOPS[k][1] && t0 <= STOPS[k + 1][1]) {
        const f = (t0 - STOPS[k][1]) / (STOPS[k + 1][1] - STOPS[k][1]);
        col = lerp(STOPS[k][0], STOPS[k + 1][0], f);
        break;
      }
    }
    segs.push(
      <path
        key={i}
        d={`M ${x0.toFixed(1)} ${y0.toFixed(1)} A ${r} ${r} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`}
        stroke={col}
        strokeWidth={sw}
        fill="none"
      />,
    );
  }
  const ang = a0 + (a1 - a0) * FRACTION[regime];
  const nx = cx + (r - 22 * scale) * Math.cos(ang);
  const ny = cy + (r - 22 * scale) * Math.sin(ang);

  // Zone labels around the arc (all five zones), at the zone centres.
  const ZONE_LABELS: [string, number, string][] = [
    ['Ext. Fear', 0.08, '#10b981'],
    ['Fear', 0.29, '#65a30d'],
    ['Neutral', 0.5, '#d97706'],
    ['Greed', 0.71, '#f97316'],
    ['Ext. Greed', 0.92, '#ef4444'],
  ];
  const rLbl = r + sw / 2 + 11 * scale;
  const labels = ZONE_LABELS.map(([txt, frac, color]) => {
    const aa = a0 + (a1 - a0) * frac;
    const c = Math.cos(aa);
    const lx = cx + rLbl * c;
    const ly = cy + rLbl * Math.sin(aa);
    const anchor = c < -0.25 ? 'end' : c > 0.25 ? 'start' : 'middle';
    return (
      <text
        key={txt}
        x={lx.toFixed(1)}
        y={ly.toFixed(1)}
        fill={color}
        fontSize={7.6 * scale}
        fontWeight={700}
        textAnchor={anchor}
        dominantBaseline="middle"
      >
        {txt}
      </text>
    );
  });

  // Pad the viewBox so the side/top labels are never clipped (the wheel keeps the
  // requested size; padding only adds label room around it).
  const padX = 52 * scale;
  const padTop = 16 * scale;
  return (
    <svg
      width={Math.round(W + 2 * padX)}
      height={Math.round(H + padTop)}
      viewBox={`${(-padX).toFixed(1)} ${(-padTop).toFixed(1)} ${(W + 2 * padX).toFixed(1)} ${(H + padTop).toFixed(1)}`}
      aria-hidden="true"
    >
      {segs}
      {labels}
      <line
        x1={cx}
        y1={cy}
        x2={nx.toFixed(1)}
        y2={ny.toFixed(1)}
        stroke="#0b1f3a"
        strokeWidth={3.5 * scale}
        strokeLinecap="round"
      />
      <circle cx={cx} cy={cy} r={6 * scale} fill="#0b1f3a" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Signal definitions (ported from the mockup; names match the backend factor
// labels so the live state resolves). Icons are inline SVG like the reference.
// ---------------------------------------------------------------------------
type BiasKind = 'greed' | 'fear' | 'rev';
interface Sig {
  name: string;
  color: string;
  bias: BiasKind;
  desc: string;
  icon: React.ReactNode;
}
const I = (children: React.ReactNode) => (
  <svg
    width="22"
    height="22"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.7"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    {children}
  </svg>
);
const E = '#10b981';
const R = '#ef4444';
const B = '#2563eb';
const A = '#f59e0b';
const SIGNALS: Sig[] = [
  {
    name: 'Nifty Trend',
    color: E,
    bias: 'greed',
    desc: 'How the Nifty 50 moved today. A rising market usually reflects optimism; a falling one reflects caution.',
    icon: I(
      <>
        <path d="M3 17 L9 11 L13 15 L21 6" />
        <path d="M16 6 H21 V11" />
      </>,
    ),
  },
  {
    name: 'Market Breadth',
    color: A,
    bias: 'greed',
    desc: 'How many stocks rose versus fell. Broad gains signal confidence; gains in only a few signal a narrow, nervous market.',
    icon: I(
      <>
        <circle cx="8" cy="9" r="3" />
        <circle cx="16" cy="9" r="3" />
        <path d="M3 20 c0-3 2.5-5 5-5 s5 2 5 5 M13 20 c0-3 2.5-5 5-5 s5 2 5 5" />
      </>,
    ),
  },
  {
    name: 'India VIX',
    color: B,
    bias: 'fear',
    desc: "The market's 'nervousness meter' — how big a swing traders expect ahead. Low VIX means calm; high VIX means anxious.",
    icon: I(<path d="M12 3 L20 6 V12 C20 17 16 20 12 21 C8 20 4 17 4 12 V6 Z" />),
  },
  {
    name: 'FII Flows',
    color: E,
    bias: 'greed',
    desc: 'How much money foreign investors put into or pulled out of the market today. Heavy inflows lift the mood; outflows drag it down.',
    icon: I(<path d="M7 4 V20 M7 4 L3 8 M7 4 L11 8 M17 20 V4 M17 20 L13 16 M17 20 L21 16" />),
  },
  {
    name: 'Global Indices',
    color: E,
    bias: 'greed',
    desc: 'How major world markets (like the US S&P 500) moved. Strong global markets tend to lift Indian sentiment.',
    icon: I(
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12 H21 M12 3 C14.5 6 14.5 18 12 21 C9.5 18 9.5 6 12 3" />
      </>,
    ),
  },
  {
    name: 'DII Flows',
    color: E,
    bias: 'greed',
    desc: 'How much domestic institutions (mutual funds, insurers) put in or took out. Steady local inflows support the mood.',
    icon: I(
      <>
        <rect x="4" y="8" width="16" height="13" rx="1" />
        <path d="M9 8 V5 H15 V8 M4 13 H20 M12 13 V21" />
      </>,
    ),
  },
  {
    name: 'US 10Y Yield',
    color: A,
    bias: 'fear',
    desc: 'The interest rate on US government bonds. When high, money tends to leave riskier markets like India; lower is friendlier.',
    icon: I(<path d="M3 21 H21 M5 21 V10 M10 21 V10 M14 21 V10 M19 21 V10 M3 10 L12 4 L21 10" />),
  },
  {
    name: 'Brent Crude',
    color: A,
    bias: 'fear',
    desc: 'The global oil price. India imports most of its oil, so expensive oil pressures the economy; cheaper oil is a tailwind.',
    icon: I(<path d="M12 3 C12 3 5 11 5 16 a7 7 0 0 0 14 0 C19 11 12 3 12 3 Z" />),
  },
  {
    name: 'USD/INR',
    color: R,
    bias: 'rev',
    desc: 'The rupee versus the dollar. A strengthening rupee signals inflows and confidence; a weakening rupee signals caution.',
    icon: I(<path d="M7 5 H17 M7 9 H17 M7 5 C11 5 13 6.5 13 9 C13 11.5 11 13 7 13 H10 L17 20" />),
  },
  {
    name: 'Put-Call Ratio',
    color: B,
    bias: 'rev',
    desc: 'An options-market gauge of positioning, read in reverse: very high (lots of protection bought) often marks fear; very low marks greed.',
    icon: I(
      <>
        <path d="M12 3 L20 6 V12 C20 17 16 20 12 21 C8 20 4 17 4 12 V6 Z" />
        <path d="M9 12 L11 14 L15 9" />
      </>,
    ),
  },
  {
    name: 'News Sentiment',
    color: E,
    bias: 'greed',
    desc: 'The overall tone of recent market-news headlines, read as positive, neutral, or negative — a positive tone lifts the mood, a negative one weighs on it.',
    icon: I(
      <>
        <rect x="3" y="5" width="14" height="15" rx="1" />
        <path d="M17 9 H21 V18 a2 2 0 0 1 -2 2 M6 9 H13 M6 12 H13 M6 15 H10" />
      </>,
    ),
  },
];

const BIAS: Record<BiasKind, { cls: string; label: string }> = {
  greed: { cls: s.biasGreed, label: '▲ Toward greed' },
  fear: { cls: s.biasFear, label: '▼ Toward fear' },
  rev: { cls: s.biasRev, label: '⇄ Read in reverse' },
};

const TIER_WORD: Record<MoodFactorTier, string> = {
  strong: 'Strong',
  moderate: 'Moderate',
  slight: 'Slight',
};
const TIER_W: Record<MoodFactorTier, number> = { strong: 92, moderate: 60, slight: 34 };
const BAND_DOTS: Record<string, number> = { high: 4, medium: 3, low: 2, insufficient_data: 1 };

interface Role {
  side: 'supporting' | 'counterweight';
  tier: MoodFactorTier;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function MoodPage() {
  const { data, isLoading, isError, error, refetch } = useMoodCurrent();
  const { data: history } = useMoodHistory(180);
  const { data: macroQuotes } = useMacroQuotes();
  const { data: breadth } = useMarketBreadth();

  const quoteMap = React.useMemo(
    () => new Map((macroQuotes ?? []).map((q) => [q.key, q])),
    [macroQuotes],
  );

  const yesterdayRegime: Regime | null = React.useMemo(() => {
    if (!data || !history) return null;
    const prior = history.find((h) => h.snapshot_date !== data.snapshot_date);
    return prior ? prior.regime : null;
  }, [data, history]);

  const roles = React.useMemo(() => {
    const m = new Map<string, Role>();
    data?.contributing_factors.forEach((f) => m.set(f.label, { side: 'supporting', tier: f.tier }));
    data?.contradicting_factors.forEach((f) =>
      m.set(f.label, { side: 'counterweight', tier: f.tier }),
    );
    return m;
  }, [data]);

  const is404 = isError && error instanceof ApiError && error.problem.status === 404;
  const unavailable =
    !!data && (data.data_quality === 'unavailable' || data.regime === 'data_unavailable');

  return (
    <MaybeShell maxWidth="wide">
      <div className={s.root}>
        <div className={s.wrap}>
          {/* BRAND BAR */}
          <div className={s.brandbar}>
            <span className={s.mark}>
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#fff"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M3 17 L9 11 L13 15 L21 6" />
                <path d="M16 6 H21 V11" />
              </svg>
            </span>
            <div style={{ minWidth: 0 }}>
              <div className={s.bbName}>
                DhanRadar Market Mood Index <span style={{ color: '#2563eb' }}>(DMMI)</span>
              </div>
              <div className={`${s.bbTag} ${s.mono}`}>
                Educational sentiment gauge · India markets
              </div>
            </div>
            {data && data.snapshot_at && (
              <span className={s.bbLive}>
                <span className={s.liveDot} /> Updated {relativeTime(data.snapshot_at)}
              </span>
            )}
          </div>

          {isLoading && (
            <div className={s.hero}>
              <Skeleton className="h-[140px] w-[240px] rounded-lg" />
              <div className="flex flex-col gap-3">
                <Skeleton className="h-5 w-64" />
                <Skeleton className="h-4 w-full max-w-md" />
                <Skeleton className="h-4 w-40" />
              </div>
            </div>
          )}

          {(is404 || unavailable) && (
            <EmptyState
              icon={<Compass size={28} aria-hidden="true" />}
              title="Market mood is being computed"
              description="Check back shortly — the next read publishes at 9:00 AM and 4:00 PM IST."
            />
          )}

          {isError && !is404 && (
            <ErrorCard
              message="Could not load market mood. Please try again."
              onRetry={() => void refetch()}
            />
          )}

          {data && !unavailable && (
            <>
              {/* HERO */}
              <section className={s.hero}>
                <div className={s.heroGauge}>
                  <Gauge regime={data.regime} size={338} />
                  <div className={s.heroState} style={{ color: HEX[data.regime] }}>
                    {WORD[data.regime]}
                  </div>
                  <div className={`${s.heroSub} ${s.mono}`}>Educational DMMI index</div>
                </div>
                <div className={s.heroRight}>
                  <div className={s.trendLine}>
                    {yesterdayRegime && (
                      <>
                        <span>
                          Yesterday: <b>{WORD[yesterdayRegime]}</b>
                        </span>
                        <span style={{ color: '#94a3b8' }}>→</span>
                      </>
                    )}
                    <span>
                      Today: <b style={{ color: HEX[data.regime] }}>{WORD[data.regime]}</b>
                    </span>
                    {data.trend && (
                      <span
                        className={`${s.trendPill} ${s.mono} ${
                          data.trend === 'deteriorating'
                            ? s.down
                            : data.trend === 'stable'
                              ? s.flat
                              : ''
                        }`}
                      >
                        {data.trend === 'improving'
                          ? '↗ Trend rising'
                          : data.trend === 'deteriorating'
                            ? '↘ Trend easing'
                            : '→ Holding steady'}
                      </span>
                    )}
                  </div>
                  {/* Short plain-language pointers (replaces the long commentary). */}
                  <ul className={s.heroBullets}>
                    <li>
                      Mood is{' '}
                      <b style={{ color: HEX[data.regime] }}>{WORD[data.regime]}</b> today, with{' '}
                      {data.confidence_band === 'insufficient_data' ? 'low' : data.confidence_band}{' '}
                      confidence.
                    </li>
                    {data.contributing_factors.length > 0 && (
                      <li>
                        Lifting the mood:{' '}
                        <b>
                          {data.contributing_factors
                            .slice(0, 3)
                            .map((f) => f.label)
                            .join(', ')}
                        </b>
                        .
                      </li>
                    )}
                    {data.contradicting_factors.length > 0 && (
                      <li>
                        Holding it back:{' '}
                        <b>
                          {data.contradicting_factors
                            .slice(0, 2)
                            .map((f) => f.label)
                            .join(', ')}
                        </b>
                        .
                      </li>
                    )}
                    <li>A plain read of the overall tone — not a prediction or a tip to act on.</li>
                  </ul>
                  <div className={`${s.conf} ${s.mono}`}>
                    <span>Confidence</span>
                    <span className={s.confDots}>
                      {[0, 1, 2, 3].map((i) => (
                        <i
                          key={i}
                          className={i < (BAND_DOTS[data.confidence_band] ?? 1) ? s.on : ''}
                        />
                      ))}
                    </span>
                    <span style={{ textTransform: 'capitalize' }}>
                      {data.confidence_band === 'insufficient_data' ? 'Low' : data.confidence_band}{' '}
                      confidence
                    </span>
                  </div>
                </div>
              </section>

              {/* WHAT'S DRIVING THIS */}
              <div className={s.sectionTitle}>
                <h2>What&rsquo;s driving this</h2>
                <span className={s.stSub}>Longer bar = stronger pull on today&rsquo;s reading</span>
              </div>
              <section className={s.panel}>
                <p className={s.driveHead}>
                  Supporting factors pull <b>toward</b> today&rsquo;s {WORD[data.regime]} reading;
                  counterweights pull the other way. This is what the index is weighing right now.
                </p>
                <div className={s.driveCols}>
                  <div className={`${s.driveCol} ${s.sup}`}>
                    <h4>▲ Supporting</h4>
                    {data.contributing_factors.length ? (
                      data.contributing_factors.map((f) => (
                        <DriveRow key={f.label} f={f} cls="sup" />
                      ))
                    ) : (
                      <p className={s.driveEmpty}>No supporting signals right now.</p>
                    )}
                  </div>
                  <div className={`${s.driveCol} ${s.cw}`}>
                    <h4>▼ Counterweights</h4>
                    {data.contradicting_factors.length ? (
                      data.contradicting_factors.map((f) => (
                        <DriveRow key={f.label} f={f} cls="cw" />
                      ))
                    ) : (
                      <p className={s.driveEmpty}>No counterweights right now.</p>
                    )}
                  </div>
                </div>
              </section>

              {/* HOW THE MOOD HAS MOVED */}
              <div className={s.sectionTitle}>
                <h2>How the mood has moved</h2>
              </div>
              <MovedTable
                today={data.regime}
                todayDate={data.snapshot_date}
                history={history ?? []}
              />

              {/* MOOD OVER TIME — daily / weekly / monthly toggle (DMMI styling) */}
              <PeriodsStrip
                history={history ?? []}
                todayRegime={data.regime}
                todayDate={data.snapshot_date}
              />

              {/* WHAT MOVES THE MOOD — signals grouped by today's role */}
              <div className={s.sectionTitle}>
                <h2>What moves the mood</h2>
                <span className={s.stSub}>
                  The mood is a blend of these signals — grouped by what they&rsquo;re doing today
                </span>
              </div>
              {(() => {
                const supporting = SIGNALS.filter((g) => roles.get(g.name)?.side === 'supporting');
                const counter = SIGNALS.filter((g) => roles.get(g.name)?.side === 'counterweight');
                const awaiting = SIGNALS.filter((g) => !roles.get(g.name));
                const groups: { key: string; label: string; dot: string; items: Sig[] }[] = [
                  { key: 'sup', label: 'Supporting the mood', dot: '#10b981', items: supporting },
                  { key: 'cw', label: 'Counterweights', dot: '#ef4444', items: counter },
                  { key: 'aw', label: 'Awaiting data', dot: '#94a3b8', items: awaiting },
                ];
                return groups
                  .filter((grp) => grp.items.length > 0)
                  .map((grp) => (
                    <React.Fragment key={grp.key}>
                      <div className={`${s.groupHead} ${s.mono}`}>
                        <span className={s.ghDot} style={{ background: grp.dot }} />
                        {grp.label}
                      </div>
                      <div className={s.signalGrid}>
                        {grp.items.map((sig) => (
                          <SignalCard
                            key={sig.name}
                            sig={sig}
                            role={roles.get(sig.name)}
                            quote={quoteMap.get(SIG_QUOTE[sig.name] ?? '')}
                            breadth={breadth}
                          />
                        ))}
                      </div>
                    </React.Fragment>
                  ));
              })()}

              {/* HOW TO READ + COMES TOGETHER */}
              <div className={s.sectionTitle}>
                <h2>How to read it</h2>
                <span className={s.stSub}>The scale, and how the signals add up</span>
              </div>
              <div className={s.twoCol}>
                {/* Scale */}
                <div className={s.panel}>
                  <h3>How to read the scale</h3>
                  <p className={s.pSub}>
                    Left is fear, right is greed. Today&rsquo;s read sits where the marker points.
                  </p>
                  <div className={s.scale}>
                    <div className={s.scaleTrack} />
                    <div className={s.scaleMarker} style={{ left: `${MARKER_PCT[data.regime]}%` }}>
                      <span className={`${s.markerPill} ${s.mono}`}>{WORD[data.regime]}</span>
                      <span className={s.markerDot} />
                    </div>
                    <div className={s.scaleTicks}>
                      <span className={s.tick}>
                        <span className={s.tickLbl} style={{ color: '#10b981' }}>
                          Extreme Fear
                        </span>
                      </span>
                      <span className={s.tick}>
                        <span className={s.tickLbl} style={{ color: '#65a30d' }}>
                          Fear
                        </span>
                      </span>
                      <span className={s.tick}>
                        <span className={s.tickLbl} style={{ color: '#334155' }}>
                          Neutral
                        </span>
                      </span>
                      <span className={s.tick}>
                        <span className={s.tickLbl} style={{ color: '#f97316' }}>
                          Greed
                        </span>
                      </span>
                      <span className={s.tick}>
                        <span className={s.tickLbl} style={{ color: '#ef4444' }}>
                          Extreme Greed
                        </span>
                      </span>
                    </div>
                  </div>
                  <div className={s.zones}>
                    <div className={`${s.zone} ${s.zFear}`}>
                      <b>Fear side</b>
                      <br />
                      Cautious mood
                    </div>
                    <div className={`${s.zone} ${s.zNeu}`}>
                      <b>Middle</b>
                      <br />
                      Balanced
                    </div>
                    <div className={`${s.zone} ${s.zGreed}`}>
                      <b>Greed side</b>
                      <br />
                      Exuberant
                    </div>
                  </div>
                </div>

                {/* Comes together — every contributing signal, compact */}
                <div className={s.panel}>
                  <h3>How it comes together</h3>
                  <p className={s.pSub}>
                    Every signal pulling the mood today — green leans greed, red leans fear. Together
                    they make the zone on the right.
                  </p>
                  <div className={s.combine}>
                    <div className={s.chips}>
                      {[
                        ...data.contributing_factors.map((f) => ({ f, support: true })),
                        ...data.contradicting_factors.map((f) => ({ f, support: false })),
                      ].map(({ f, support }) => {
                        const q = quoteMap.get(SIG_QUOTE[f.label] ?? '');
                        const valStr =
                          f.label === 'Market Breadth' && breadth
                            ? `${breadth.advances}/${breadth.declines}`
                            : q
                              ? fmtQuoteCompact(q.key, q.value)
                              : '';
                        const col = support ? '#10b981' : '#ef4444';
                        return (
                          <div key={f.label} className={s.cchip}>
                            <div className={s.ccName}>{f.label}</div>
                            <div className={s.ccVal} style={{ color: col }}>
                              {valStr && <span className={s.mono}>{valStr} </span>}
                              {support ? '▲' : '▼'}
                            </div>
                          </div>
                        );
                      })}
                      {data.contributing_factors.length + data.contradicting_factors.length ===
                        0 && <div className={s.driveEmpty}>Signals updating…</div>}
                    </div>
                    <div className={s.combineArrow}>→</div>
                    <div className={s.result}>
                      <div className={`${s.rLbl} ${s.mono}`}>Today&rsquo;s mood</div>
                      <div className={s.rState} style={{ color: HEX[data.regime] }}>
                        {WORD[data.regime]}
                      </div>
                    </div>
                  </div>
                  <div className={s.combineKey}>
                    <span>
                      <span className={s.keyDot} style={{ background: '#10b981' }} /> Green = leaning
                      greed
                    </span>
                    <span>
                      <span className={s.keyDot} style={{ background: '#ef4444' }} /> Red = leaning
                      fear
                    </span>
                  </div>
                </div>
              </div>

              {/* DISCLOSURE — the single SEBI-required bundle (non-neg #9), tied to the in-force
                  disclaimer version. The standing site footer (MaybeShell/AppShell) is the common
                  footer for all users; no extra page-level disclaimer here. */}
              <div style={{ marginTop: 20 }}>
                <DisclosureBundle disclosure={data.disclosure} notAdvice={data.not_advice} />
              </div>
            </>
          )}
        </div>
      </div>
    </MaybeShell>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function DriveRow({ f, cls }: { f: MoodFactor; cls: 'sup' | 'cw' }) {
  return (
    <div className={s.drow}>
      <div className={s.drowTop}>
        <span className={s.drowName}>
          {cls === 'sup' ? '+' : '–'} {f.label}
        </span>
        <span className={`${s.drowStrength} ${s.mono}`}>{TIER_WORD[f.tier]}</span>
      </div>
      <div className={`${s.dbar} ${cls === 'sup' ? s.sup : s.cw}`}>
        <span style={{ width: `${TIER_W[f.tier]}%` }} />
      </div>
    </div>
  );
}

// Signal name → macro-quote key, and per-signal value formatting (public data).
const SIG_QUOTE: Record<string, string> = {
  'Nifty Trend': 'nifty_trend',
  'India VIX': 'india_vix',
  'Global Indices': 'global_indices',
  'US 10Y Yield': 'us_bond_10y',
  'Brent Crude': 'oil_brent',
  'USD/INR': 'usd_inr',
};
const QUOTE_PREFIX: Record<string, string> = { oil_brent: '$', usd_inr: '₹' };
const QUOTE_SUFFIX: Record<string, string> = { us_bond_10y: '%' };
function fmtQuoteVal(key: string, value: number): string {
  return (
    (QUOTE_PREFIX[key] ?? '') +
    value.toLocaleString('en-IN', { maximumFractionDigits: 2 }) +
    (QUOTE_SUFFIX[key] ?? '')
  );
}
// Compact form (no decimals) for the dense "how it comes together" chips.
function fmtQuoteCompact(key: string, value: number): string {
  return (
    (QUOTE_PREFIX[key] ?? '') +
    Math.round(value).toLocaleString('en-IN') +
    (QUOTE_SUFFIX[key] ?? '')
  );
}

function SignalCard({
  sig,
  role,
  quote,
  breadth,
}: {
  sig: Sig;
  role?: Role;
  quote?: MacroQuote;
  breadth?: MarketBreadth;
}) {
  const bias = BIAS[sig.bias];
  // Real public market value for this signal, when available (Yahoo public data).
  let liveVal: React.ReactNode = null;
  if (sig.name === 'Market Breadth' && breadth) {
    const up = breadth.advances >= breadth.declines;
    liveVal = (
      <span className={`${s.exVal} ${s.mono} ${up ? s.up : s.down}`}>
        {breadth.advances.toLocaleString('en-IN')} adv / {breadth.declines.toLocaleString('en-IN')}{' '}
        dec
      </span>
    );
  } else if (quote) {
    const up = quote.change_pct >= 0;
    liveVal = (
      <span className={`${s.exVal} ${s.mono} ${up ? s.up : s.down}`}>
        {fmtQuoteVal(quote.key, quote.value)}{' '}
        <span style={{ fontSize: 11 }}>
          {up ? '▲' : '▼'} {fmtPct(quote.change_pct)}
        </span>
      </span>
    );
  }
  return (
    <div className={s.signal}>
      <span className={s.sigIco} style={{ background: sig.color + '1a', color: sig.color }}>
        {sig.icon}
      </span>
      <div className={s.sigBody}>
        <div className={s.sigName}>
          {sig.name}
          <span className={`${s.bias} ${bias.cls} ${s.mono}`}>{bias.label}</span>
        </div>
        <div className={s.sigDesc}>{sig.desc}</div>
      </div>
      <div className={s.ex}>
        <span className={`${s.exLbl} ${s.mono}`}>Today</span>
        {liveVal ??
          (role ? (
            <span className={`${s.exVal} ${role.side === 'supporting' ? s.up : s.down}`}>
              {role.side === 'supporting' ? '↑ Supporting' : '↓ Counterweight'}
            </span>
          ) : (
            <span className={`${s.exVal} ${s.neu}`}>Awaiting data</span>
          ))}
        {role && (
          <span style={{ fontSize: 11, color: '#64748b' }}>
            {role.side === 'supporting' ? 'Supporting' : 'Counterweight'} · {TIER_WORD[role.tier]}
          </span>
        )}
      </div>
    </div>
  );
}

// Signed % change, e.g. "+0.46%" — public market data (NOT the mood score).
const fmtPct = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(2)}%`;

function MovedTable({
  today,
  todayDate,
  history,
}: {
  today: Regime;
  todayDate: string;
  history: { snapshot_date: string; regime: Regime }[];
}) {
  // Closest snapshot to a target days-ago offset.
  const at = (daysAgo: number): Regime | null => {
    if (!history.length) return null;
    const target = new Date(todayDate);
    target.setDate(target.getDate() - daysAgo);
    const ts = target.getTime();
    let best: { d: number; regime: Regime } | null = null;
    for (const h of history) {
      if (h.snapshot_date === todayDate) continue;
      const d = Math.abs(new Date(h.snapshot_date).getTime() - ts);
      if (best === null || d < best.d) best = { d, regime: h.regime };
    }
    return best ? best.regime : null;
  };
  const rows = ([
    ['Since yesterday', at(1)],
    ['Since last week', at(7)],
    ['Since last month', at(30)],
  ] as [string, Regime | null][]).filter((r) => r[1] !== null);
  if (!rows.length) return null;
  return (
    <div className={s.moved}>
      {rows.map(([label, prev]) => (
        <div key={label} className={s.movedRow}>
          <span className={s.ml}>{label}</span>
          <span className={s.mr}>
            <span className={`${s.tlabel} ${s.mono}`} style={tlabelStyle(prev as Regime)}>
              {WORD[prev as Regime]}
            </span>
            <span style={{ color: '#94a3b8' }}>→</span>
            <span className={`${s.tlabel} ${s.mono}`} style={tlabelStyle(today)}>
              {WORD[today]}
            </span>
          </span>
        </div>
      ))}
      <div className={s.movedFoot}>
        A plain history of the sentiment label over time — no scores, and not a prediction of where
        it goes next.
      </div>
    </div>
  );
}

// --- Mood-over-time: daily / weekly / monthly buckets (DMMI-styled toggle) ---
type View = 'monthly' | 'weekly' | 'daily';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const VIEW_COUNT: Record<View, number> = { monthly: 6, weekly: 8, daily: 12 };

function startOfWeek(d: Date): Date {
  const x = new Date(d);
  const day = (x.getDay() + 6) % 7; // Monday = 0
  x.setDate(x.getDate() - day);
  x.setHours(0, 0, 0, 0);
  return x;
}
function bucketKey(d: Date, v: View): string {
  if (v === 'monthly') return `${d.getFullYear()}-${d.getMonth()}`;
  if (v === 'weekly') return startOfWeek(d).toISOString().slice(0, 10);
  return d.toISOString().slice(0, 10);
}
function bucketLabel(d: Date, v: View): string {
  if (v === 'monthly') return MONTHS[d.getMonth()];
  const ref = v === 'weekly' ? startOfWeek(d) : d;
  return `${ref.getDate()} ${MONTHS[ref.getMonth()]}`;
}
function modeRegime(rs: Regime[]): Regime {
  const counts = new Map<Regime, number>();
  for (const r of rs) counts.set(r, (counts.get(r) ?? 0) + 1);
  let best = rs[0];
  let bestN = 0;
  for (const [r, n] of counts) {
    if (n > bestN) {
      best = r;
      bestN = n;
    }
  }
  return best;
}

function PeriodsStrip({
  history,
  todayRegime,
  todayDate,
}: {
  history: { snapshot_date: string; regime: Regime }[];
  todayRegime: Regime;
  todayDate: string;
}) {
  const [view, setView] = React.useState<View>('monthly');
  const cells = React.useMemo(() => {
    if (!history.length) return [];
    const groups = new Map<string, { date: Date; regimes: Regime[] }>();
    for (const h of history) {
      const d = new Date(h.snapshot_date);
      if (Number.isNaN(d.getTime())) continue;
      const k = bucketKey(d, view);
      const g = groups.get(k);
      if (g) g.regimes.push(h.regime);
      else groups.set(k, { date: d, regimes: [h.regime] });
    }
    const todayKey = bucketKey(new Date(todayDate), view);
    return [...groups.entries()]
      .map(([key, g]) => ({
        key,
        date: g.date,
        regime: key === todayKey ? todayRegime : modeRegime(g.regimes),
        label: key === todayKey ? 'Now' : bucketLabel(g.date, view),
        today: key === todayKey,
      }))
      .sort((a, b) => a.date.getTime() - b.date.getTime())
      .slice(-VIEW_COUNT[view]);
  }, [history, view, todayRegime, todayDate]);

  if (!cells.length) return null;
  return (
    <>
      <div className={s.sectionTitle}>
        <h2>Mood over time</h2>
        <span className={s.stSub}>Where the mood sat — switch the window</span>
      </div>
      <div className={s.periodsPanel}>
        <div className={s.periodToggle}>
          {(['monthly', 'weekly', 'daily'] as View[]).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={`${s.periodBtn}${view === v ? ' ' + s.periodBtnOn : ''}`}
            >
              {v.charAt(0).toUpperCase() + v.slice(1)}
            </button>
          ))}
        </div>
        <div className={s.monthStrip}>
          {cells.map((m) => (
            <div key={m.key} className={`${s.mcell}${m.today ? ' ' + s.today : ''}`}>
              <div className={`${s.mName} ${s.mono}`}>{m.label}</div>
              <div className={s.mDisc} style={{ background: HEX[m.regime] }} />
              <div className={s.mState} style={{ color: HEX[m.regime] }}>
                {WORD[m.regime]}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

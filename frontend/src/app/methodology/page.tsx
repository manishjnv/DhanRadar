/**
 * /methodology — Public transparency page.
 *
 * Server Component (NO 'use client'); NOT inside the (app) route group →
 * no AuthGuard, same public posture as /learn/concepts and /mood.
 * Chrome (header + standing <Disclaimer/>) is provided by MaybeShell.
 *
 * This page is the canonical destination for methodology_url published in:
 *   - backend/dhanradar/scoring/ranking_configs_v1.json
 *   - the compliance disclosure bundle (not_advice / disclaimer copy)
 *
 * Compliance invariants honoured here:
 *   - NON-NEG #1: zero advisory verbs — educational descriptions only.
 *   - NON-NEG #2: zero numerics in the DOM — no raw scores, factor weights,
 *     percentage-as-a-score, fair values, or numeric thresholds.
 *   - NON-NEG #9: DisclosureBundle rendered adjacent to the content;
 *     standing <Disclaimer/> is supplied by MaybeShell.
 *   - Static content only — no backend fetch (avoids SSR build-time
 *     ECONNREFUSED; see RCA "SSR page build-time fetch ECONNREFUSED").
 */
import type { Metadata } from 'next';
import { Card, CardBody } from '@/components/ui/Card';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { MaybeShell } from '@/components/ui/MaybeShell';

// Render per-request — consistent with all other public MaybeShell pages.
export const dynamic = 'force-dynamic';

// ---------------------------------------------------------------------------
// Static SEO metadata
// ---------------------------------------------------------------------------
export const metadata: Metadata = {
  title: 'How DhanRadar Works — Methodology',
  description:
    'How DhanRadar describes mutual fund behaviour — the label set, confidence bands, the factors considered, data sources, and the boundaries of what this platform is and is not. Educational content only, not investment advice.',
  openGraph: {
    title:       'How DhanRadar Works — Methodology',
    description: 'How DhanRadar describes mutual fund behaviour — the label set, confidence bands, the factors considered, data sources, and the boundaries of what this platform is and is not.',
    type:        'website',
    siteName:    'DhanRadar',
  },
};

// ---------------------------------------------------------------------------
// Page — Server Component, no hooks, no fetch
// ---------------------------------------------------------------------------
export default function MethodologyPage() {
  return (
    <MaybeShell>
      {/* Page heading */}
      <div className="mb-8">
        <p className="text-caption text-ink-muted uppercase tracking-wide mb-1">
          Transparency
        </p>
        <h1 className="text-h2 text-ink">How DhanRadar Works</h1>
        <p className="text-small text-ink-secondary mt-2">
          A plain-language explanation of how mutual fund behaviour is described,
          what the labels mean, and what DhanRadar is — and is not.
        </p>
      </div>

      <div className="space-y-6">

        {/* ------------------------------------------------------------------ */}
        {/* 1. What this is                                                     */}
        {/* ------------------------------------------------------------------ */}
        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">What DhanRadar is</h2>
            <p className="text-small text-ink-secondary leading-relaxed">
              DhanRadar is a SEBI-educational market-intelligence platform for Indian
              retail investors. It observes and describes patterns in a mutual fund&apos;s
              recent behaviour — how it has been performing relative to its peers, how
              consistent that behaviour has been, and how much confidence the available
              data supports. DhanRadar explains; it does not direct. Nothing on this
              platform is a recommendation, a forecast, or advice of any kind. All
              labels and assessments are educational observations derived from a
              published rule table applied to official public data.
            </p>
          </CardBody>
        </Card>

        {/* ------------------------------------------------------------------ */}
        {/* 2. The labels & what they mean                                      */}
        {/* ------------------------------------------------------------------ */}
        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">
              The labels and what they mean
            </h2>
            <p className="text-small text-ink-secondary mb-4 leading-relaxed">
              DhanRadar assigns one of five labels to describe a fund&apos;s observable
              recent behaviour. These are pattern descriptions — not signals to act,
              not predictions of what will happen next, and not assessments of whether
              a fund is right for any particular investor. The label is derived from a
              published rule table, not a hidden numerical formula.
            </p>

            <div className="space-y-4">

              <div className="border-l-2 border-line pl-4">
                <p className="text-small font-semibold text-ink font-mono">in_form</p>
                <p className="text-small text-ink-secondary mt-1 leading-relaxed">
                  The fund has been behaving consistently well across multiple
                  dimensions relative to its SEBI category peers over the observed
                  period. This describes a pattern of recent behaviour — it is an
                  observation, not an endorsement or a signal to invest.
                </p>
              </div>

              <div className="border-l-2 border-line pl-4">
                <p className="text-small font-semibold text-ink font-mono">on_track</p>
                <p className="text-small text-ink-secondary mt-1 leading-relaxed">
                  The fund&apos;s recent behaviour is broadly in line with what would be
                  expected for its category. No strong divergence — positive or
                  negative — is evident in the observed data. This is a neutral
                  descriptive observation.
                </p>
              </div>

              <div className="border-l-2 border-line pl-4">
                <p className="text-small font-semibold text-ink font-mono">off_track</p>
                <p className="text-small text-ink-secondary mt-1 leading-relaxed">
                  The fund&apos;s recent behaviour shows signs of diverging unfavourably
                  from its category peers in one or more observed dimensions. This
                  describes a pattern in recent data — it is not a prediction and does
                  not indicate what the fund will do in the future.
                </p>
              </div>

              <div className="border-l-2 border-line pl-4">
                <p className="text-small font-semibold text-ink font-mono">out_of_form</p>
                <p className="text-small text-ink-secondary mt-1 leading-relaxed">
                  The fund&apos;s recent behaviour shows a sustained pattern of lagging
                  its category peers across multiple observed dimensions. This is a
                  descriptive observation about the period covered by the available
                  data — not a directive and not a forecast.
                </p>
              </div>

              <div className="border-l-2 border-line pl-4">
                <p className="text-small font-semibold text-ink font-mono">
                  insufficient_data
                </p>
                <p className="text-small text-ink-secondary mt-1 leading-relaxed">
                  The available data does not meet the minimum quality or coverage
                  threshold needed to form a confident assessment. Rather than produce
                  a label that could be misleading, DhanRadar returns this state
                  explicitly. No label is assigned. This is a deliberate design
                  choice: honesty about the limits of the data is more useful than
                  a guess.
                </p>
              </div>

            </div>
          </CardBody>
        </Card>

        {/* ------------------------------------------------------------------ */}
        {/* 3. Confidence bands                                                 */}
        {/* ------------------------------------------------------------------ */}
        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">Confidence bands</h2>
            <p className="text-small text-ink-secondary mb-4 leading-relaxed">
              Every label (other than <span className="font-mono">insufficient_data</span>)
              is accompanied by a confidence band that describes how much the underlying
              data supports the assessment. Three bands are used:
            </p>

            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <span className="text-small font-semibold text-ink font-mono shrink-0 w-20">
                  high
                </span>
                <p className="text-small text-ink-secondary leading-relaxed">
                  The data is sufficient in quality and coverage to support a confident
                  assessment of the described pattern.
                </p>
              </div>
              <div className="flex items-start gap-3">
                <span className="text-small font-semibold text-ink font-mono shrink-0 w-20">
                  medium
                </span>
                <p className="text-small text-ink-secondary leading-relaxed">
                  The data is adequate but contains gaps or shorter history that reduce
                  certainty. The pattern is visible but should be read with that context.
                </p>
              </div>
              <div className="flex items-start gap-3">
                <span className="text-small font-semibold text-ink font-mono shrink-0 w-20">
                  low
                </span>
                <p className="text-small text-ink-secondary leading-relaxed">
                  The data shows a pattern but coverage or quality is limited. The
                  assessment is tentative — read it as a description of a thin
                  data picture, not as a firm characterisation.
                </p>
              </div>
            </div>

            <p className="text-small text-ink-muted mt-4 leading-relaxed">
              When confidence is too low to assign even the <span className="font-mono">low</span>{' '}
              band meaningfully, the system returns{' '}
              <span className="font-mono">insufficient_data</span> and declines to label
              rather than produce a potentially misleading result.
            </p>
          </CardBody>
        </Card>

        {/* ------------------------------------------------------------------ */}
        {/* 4. What the methodology considers                                   */}
        {/* ------------------------------------------------------------------ */}
        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">
              What the methodology considers
            </h2>
            <p className="text-small text-ink-secondary mb-4 leading-relaxed">
              Labels are derived by examining a fund&apos;s behaviour across several
              qualitative factor families. Each family asks a different question about
              the fund&apos;s recent conduct. No single factor family determines the
              label on its own — the rule table weighs the overall pattern.
            </p>

            <ul className="space-y-3">
              <li className="flex items-start gap-3">
                <span
                  className="mt-1.5 h-1.5 w-1.5 rounded-full bg-royal shrink-0"
                  aria-hidden="true"
                />
                <div>
                  <p className="text-small font-medium text-ink">
                    Consistency of returns
                  </p>
                  <p className="text-small text-ink-secondary leading-relaxed mt-0.5">
                    How steadily the fund has delivered results relative to its SEBI
                    category peers over the observed period — not the absolute level
                    of returns, but the regularity and pattern of behaviour.
                  </p>
                </div>
              </li>

              <li className="flex items-start gap-3">
                <span
                  className="mt-1.5 h-1.5 w-1.5 rounded-full bg-royal shrink-0"
                  aria-hidden="true"
                />
                <div>
                  <p className="text-small font-medium text-ink">
                    Risk-adjusted behaviour
                  </p>
                  <p className="text-small text-ink-secondary leading-relaxed mt-0.5">
                    Whether the returns observed are proportionate to the level of
                    variability in the fund&apos;s NAV history — comparing what the fund
                    achieved against the turbulence it experienced in doing so.
                  </p>
                </div>
              </li>

              <li className="flex items-start gap-3">
                <span
                  className="mt-1.5 h-1.5 w-1.5 rounded-full bg-royal shrink-0"
                  aria-hidden="true"
                />
                <div>
                  <p className="text-small font-medium text-ink">
                    Downside resilience
                  </p>
                  <p className="text-small text-ink-secondary leading-relaxed mt-0.5">
                    How the fund has behaved during periods when its category peers were
                    under stress — specifically, whether it limited losses relative to
                    the broader category experience.
                  </p>
                </div>
              </li>

              <li className="flex items-start gap-3">
                <span
                  className="mt-1.5 h-1.5 w-1.5 rounded-full bg-royal shrink-0"
                  aria-hidden="true"
                />
                <div>
                  <p className="text-small font-medium text-ink">Cost efficiency</p>
                  <p className="text-small text-ink-secondary leading-relaxed mt-0.5">
                    Whether the fund&apos;s cost structure is consistent with its
                    category and the behaviour it has delivered — costs are a
                    persistent drag on returns and are considered as part of the
                    overall pattern.
                  </p>
                </div>
              </li>

              <li className="flex items-start gap-3">
                <span
                  className="mt-1.5 h-1.5 w-1.5 rounded-full bg-royal shrink-0"
                  aria-hidden="true"
                />
                <div>
                  <p className="text-small font-medium text-ink">
                    Standing within its SEBI category peer group
                  </p>
                  <p className="text-small text-ink-secondary leading-relaxed mt-0.5">
                    All observations are made relative to the fund&apos;s SEBI-defined
                    category — not against the entire fund universe. A fund is assessed
                    against peers that share its investment mandate, making the
                    comparison meaningful.
                  </p>
                </div>
              </li>
            </ul>
          </CardBody>
        </Card>

        {/* ------------------------------------------------------------------ */}
        {/* 5. Data & freshness                                                 */}
        {/* ------------------------------------------------------------------ */}
        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">Data and freshness</h2>
            <p className="text-small text-ink-secondary mb-3 leading-relaxed">
              Labels are computed from official, publicly available sources. NAV
              history is sourced from AMFI (the Association of Mutual Funds in India)
              and carries a provenance timestamp recording when it was ingested. Every
              data point used in an assessment is traceable to its source.
            </p>
            <p className="text-small text-ink-secondary leading-relaxed">
              Data freshness is tracked explicitly. When the data underlying a label
              is stale — for example, because a fund&apos;s NAV has not been updated
              recently — DhanRadar surfaces that as a data quality signal rather than
              presenting the label as current. Stale data is flagged; it is never
              silently treated as up to date.
            </p>
          </CardBody>
        </Card>

        {/* ------------------------------------------------------------------ */}
        {/* 6. What it is NOT                                                   */}
        {/* ------------------------------------------------------------------ */}
        <Card>
          <CardBody>
            <h2 className="text-h3 font-medium text-ink mb-3">What DhanRadar is not</h2>
            <ul className="space-y-2">
              {[
                'DhanRadar is not investment advice. Nothing here tells you what to do with your money.',
                'DhanRadar does not make recommendations. It does not suggest which funds to choose or which to exit.',
                'DhanRadar does not make predictions or forecasts. A label describes what has been observed in the past; it says nothing about what will happen in the future.',
                'Past behaviour does not guarantee future results. A fund that has been in form may not remain so; a fund that has been out of form may improve.',
                'DhanRadar is not a substitute for professional financial advice. If you need guidance on your specific financial situation, consult a SEBI-registered investment adviser.',
                'This platform is for educational and informational purposes only.',
              ].map((item, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span
                    className="mt-1.5 h-1.5 w-1.5 rounded-full bg-ink-muted shrink-0"
                    aria-hidden="true"
                  />
                  <p className="text-small text-ink-secondary leading-relaxed">
                    {item}
                  </p>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>

        {/* ------------------------------------------------------------------ */}
        {/* 7. Disclosure bundle (non-neg #9)                                   */}
        {/* ------------------------------------------------------------------ */}
        <DisclosureBundle
          notAdvice="NOT INVESTMENT ADVICE — DhanRadar is a SEBI-educational platform. All labels, assessments, and descriptions are educational observations only. They do not constitute investment advice, recommendations, or inducements to transact. Past patterns do not predict future outcomes. Consult a SEBI-registered investment adviser before making any financial decision."
          disclosure="Labels are derived from official public data (AMFI NAV history and related sources) using a published rule table. No numeric score is exposed to the user. Confidence bands describe data quality — not the magnitude of any underlying number."
          className="px-1"
        />

      </div>
    </MaybeShell>
  );
}

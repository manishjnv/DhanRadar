'use client';

/**
 * SipCalculator — generic, standalone EDUCATIONAL compounding calculator.
 *
 * COMPLIANCE (DhanRadar-Goal-Planning-Calculator + non-advisory boundary):
 *  - Calculate · Illustrate · Educate · NEVER advise. No fund/scheme/SIP-amount
 *    recommendation, no "invest now"/"start SIP" CTA, no buy/sell/hold language.
 *  - The return rate is the USER's assumption, surfaced as such — never an
 *    expected/likely/assured value, never tied to a DhanRadar fund/score/mood.
 *  - Result is framed conditionally ("IF your assumed rate holds…") and paired
 *    with a sensitivity strip so a single optimistic number never stands alone
 *    (Inv. 5/11). The mandatory disclaimer renders right next to the result.
 *  - Numbers shown are the USER's own computed figures, not any proprietary
 *    score — the no-numeric-in-DOM rule does not apply here.
 */

import * as React from 'react';

import { Card, CardBody } from '@/components/ui/Card';
import { Field, Input } from '@/components/ui/Input';
import { computeSip, formatInr, MAX_RATE_PCT, MAX_YEARS } from './sip-math';

// Mandatory disclaimer copy — rendered next to the result. Exported so the test
// asserts the exact string is present (compliance regression guard).
export const CALC_DISCLAIMER =
  'Illustrative only — not a projection or guarantee. The return rate is an ' +
  'assumption you choose, not a DhanRadar prediction, and is not assured. ' +
  'Mutual fund investments are subject to market risk. Educational, not ' +
  'investment advice.';

// Sensible defaults (labeled assumptions, not predictions).
const DEFAULT_SIP = 10_000;
const DEFAULT_LUMP = 0;
const DEFAULT_YEARS = 10;
const DEFAULT_RATE = 12;

/** Parse a numeric field, treating blank/garbage as 0 (never NaN into state). */
function toNumber(raw: string): number {
  const n = Number(raw);
  return Number.isFinite(n) ? n : 0;
}

/** Pick ≤ 6 evenly-spaced year points (incl. the last) for the compact chart. */
function milestones<T>(series: T[]): T[] {
  if (series.length <= 6) return series;
  const step = (series.length - 1) / 5;
  const out: T[] = [];
  for (let k = 0; k <= 5; k += 1) out.push(series[Math.round(k * step)]);
  return out;
}

export function SipCalculator() {
  const [monthlySip, setMonthlySip] = React.useState(DEFAULT_SIP);
  const [lumpSum, setLumpSum] = React.useState(DEFAULT_LUMP);
  const [years, setYears] = React.useState(DEFAULT_YEARS);
  const [rate, setRate] = React.useState(DEFAULT_RATE);

  const result = React.useMemo(
    () => computeSip({ monthlySip, lumpSum, years, annualRatePct: rate }),
    [monthlySip, lumpSum, years, rate],
  );

  // Sensitivity: the same inputs at a lower and higher assumed rate, so the
  // point estimate reads as fragile, not as a forecast (Inv. 5/11).
  const lowerRate = Math.max(rate - 2, 0);
  const higherRate = Math.min(rate + 2, MAX_RATE_PCT);
  const lowerFv = computeSip({ monthlySip, lumpSum, years, annualRatePct: lowerRate }).futureValue;
  const higherFv = computeSip({ monthlySip, lumpSum, years, annualRatePct: higherRate }).futureValue;

  const chartPoints = milestones(result.series);
  const chartMax = Math.max(...chartPoints.map((p) => p.value), 1);

  return (
    <div className="space-y-6">
      {/* ---- Inputs ---- */}
      <Card>
        <CardBody className="space-y-5">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <Field
              id="sip-monthly"
              label="Monthly amount (₹)"
              hint="What you’d add every month. Set to 0 for a lump sum only."
            >
              <Input
                id="sip-monthly"
                type="number"
                inputMode="numeric"
                min={0}
                value={monthlySip}
                onChange={(e) => setMonthlySip(toNumber(e.target.value))}
              />
            </Field>

            <Field
              id="sip-lump"
              label="One-time amount (₹)"
              hint="A single amount added at the start. Optional."
            >
              <Input
                id="sip-lump"
                type="number"
                inputMode="numeric"
                min={0}
                value={lumpSum}
                onChange={(e) => setLumpSum(toNumber(e.target.value))}
              />
            </Field>

            <Field id="sip-years" label="Number of years" hint={`Up to ${MAX_YEARS} years.`}>
              <Input
                id="sip-years"
                type="number"
                inputMode="numeric"
                min={0}
                max={MAX_YEARS}
                value={years}
                onChange={(e) => setYears(toNumber(e.target.value))}
              />
            </Field>

            <Field
              id="sip-rate"
              label="Assumed yearly return (%)"
              hint="An assumption you choose — not a DhanRadar prediction."
            >
              <Input
                id="sip-rate"
                type="number"
                inputMode="decimal"
                min={0}
                max={MAX_RATE_PCT}
                step={0.5}
                value={rate}
                onChange={(e) => setRate(toNumber(e.target.value))}
              />
            </Field>
          </div>

          {/* Rate slider — same value, easier to explore. */}
          <div>
            <input
              type="range"
              min={0}
              max={MAX_RATE_PCT}
              step={0.5}
              value={rate}
              onChange={(e) => setRate(toNumber(e.target.value))}
              aria-label="Assumed yearly return percentage"
              className="w-full accent-royal"
            />
            <p className="text-caption text-ink-muted mt-1">
              You’ve assumed {rate}% a year. Slide to see how a different assumption changes the
              illustration.
            </p>
          </div>
        </CardBody>
      </Card>

      {/* ---- Result (conditional framing) ---- */}
      <Card>
        <CardBody className="space-y-5">
          <p className="text-small text-ink-secondary">
            If your chosen rate of {rate}% a year held for the whole period, this generic
            compounding math works out to:
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <p className="text-caption text-ink-muted">Projected value</p>
              <p
                className="text-h2 font-mono tabular-nums text-ink"
                data-testid="result-future-value"
              >
                {formatInr(result.futureValue)}
              </p>
            </div>
            <div>
              <p className="text-caption text-ink-muted">Total you put in</p>
              <p className="text-h3 font-mono tabular-nums text-ink-secondary">
                {formatInr(result.totalInvested)}
              </p>
            </div>
            <div>
              <p className="text-caption text-ink-muted">Growth on top</p>
              <p className="text-h3 font-mono tabular-nums text-ink-secondary">
                {formatInr(result.wealthGained)}
              </p>
            </div>
          </div>

          {/* Sensitivity — the same money at a lower / higher assumed rate. */}
          <div className="rounded-md border border-line bg-surface-2 p-3">
            <p className="text-caption font-medium text-ink mb-2">
              Small changes in your assumption change the result a lot
            </p>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <p className="text-caption text-ink-muted">At {lowerRate}%</p>
                <p className="text-small font-mono tabular-nums text-ink-secondary">
                  {formatInr(lowerFv)}
                </p>
              </div>
              <div>
                <p className="text-caption text-ink-muted">At {rate}% (yours)</p>
                <p className="text-small font-mono tabular-nums text-ink">
                  {formatInr(result.futureValue)}
                </p>
              </div>
              <div>
                <p className="text-caption text-ink-muted">At {higherRate}%</p>
                <p className="text-small font-mono tabular-nums text-ink-secondary">
                  {formatInr(higherFv)}
                </p>
              </div>
            </div>
            <p className="text-caption text-ink-muted mt-2">
              Real returns vary year to year and can be lower than any assumption — including zero or
              negative in a bad stretch.
            </p>
          </div>

          {/* ---- Lightweight invested-vs-value chart ---- */}
          <div>
            <p className="text-caption font-medium text-ink mb-2">
              Money in vs illustrated value over time
            </p>
            <div className="flex items-end gap-2" role="img" aria-label="Invested versus illustrated value by year">
              {chartPoints.map((p) => (
                <div key={p.year} className="flex flex-1 flex-col items-center gap-1">
                  <div className="flex h-32 w-full items-end justify-center gap-1">
                    <div
                      className="w-1/2 rounded-t-sm bg-line-strong"
                      style={{ height: `${(p.invested / chartMax) * 100}%` }}
                      title={`Year ${p.year} — put in ${formatInr(p.invested)}`}
                    />
                    <div
                      className="w-1/2 rounded-t-sm bg-royal"
                      style={{ height: `${(p.value / chartMax) * 100}%` }}
                      title={`Year ${p.year} — illustrated value ${formatInr(p.value)}`}
                    />
                  </div>
                  <span className="text-caption text-ink-muted">{p.year}y</span>
                </div>
              ))}
            </div>
            <div className="mt-2 flex items-center gap-4">
              <span className="inline-flex items-center gap-1.5 text-caption text-ink-muted">
                <span className="h-2.5 w-2.5 rounded-sm bg-line-strong" aria-hidden="true" />
                Money in
              </span>
              <span className="inline-flex items-center gap-1.5 text-caption text-ink-muted">
                <span className="h-2.5 w-2.5 rounded-sm bg-royal" aria-hidden="true" />
                Illustrated value
              </span>
            </div>
          </div>

          {/* ---- Mandatory disclaimer, next to the result ---- */}
          <p role="note" className="text-caption text-ink-muted border-t border-line pt-3">
            {CALC_DISCLAIMER}
          </p>
        </CardBody>
      </Card>

      {/* ---- Educational note: teach the concept (Inv. 10) ---- */}
      <Card>
        <CardBody className="space-y-2">
          <p className="text-small font-medium text-ink">What this shows</p>
          <p className="text-small text-ink-secondary">
            Compounding means any growth itself earns growth over time, so the longer the period,
            the larger the gap between what you put in and the illustrated value. This tool models a
            range of <em>possible</em> futures from the rate you pick — it does not predict what any
            investment will actually do, and it is not tied to any fund or rating.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}

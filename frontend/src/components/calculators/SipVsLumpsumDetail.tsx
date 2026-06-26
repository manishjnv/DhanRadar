'use client';

/**
 * SipVsLumpsumDetail — 'sip-vs-lumpsum' view (Versus): same total money,
 * same assumed return — invest all at once versus spread monthly. The
 * "winner" badge is only "for your inputs" — never a recommendation.
 *
 * COMPLIANCE: factual on the user's own figures; no advisory verbs; no
 * numeric scores or fund-specific values in the DOM.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, RangeField, AiCard, RelatedCard } from './ui';
import { computeSip, formatInr, formatInrShort } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';
import { VersusLayout, type VsOption } from './VersusLayout';

export function SipVsLumpsumDetail({ config }: { config: CalcConfig }) {
  const [total, setTotal] = React.useState(1_200_000);
  const [years, setYears] = React.useState(10);
  const [rate, setRate] = React.useState(12);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const reset = () => { setTotal(1_200_000); setYears(10); setRate(12); };

  const { lumpFv, sipFv, monthly } = React.useMemo(() => {
    const lumpFv = computeSip({ monthlySip: 0, lumpSum: total, years, annualRatePct: rate }).futureValue;
    const monthly = years > 0 ? total / (years * 12) : 0;
    const sipFv = computeSip({ monthlySip: monthly, lumpSum: 0, years, annualRatePct: rate }).futureValue;
    return { lumpFv, sipFv, monthly };
  }, [total, years, rate]);

  const lumpWins = lumpFv >= sipFv;
  const gap = Math.abs(lumpFv - sipFv);

  const options: VsOption[] = [
    {
      label: 'Lumpsum',
      headline: formatInr(lumpFv),
      headlineLabel: 'Value at the end',
      winner: lumpWins,
      rows: [
        { label: 'Invested', value: formatInr(total) },
        { label: 'Gain', value: formatInr(lumpFv - total) },
        { label: 'How', value: 'All at once, today' },
      ],
    },
    {
      label: 'SIP',
      headline: formatInr(sipFv),
      headlineLabel: 'Value at the end',
      winner: !lumpWins,
      rows: [
        { label: 'Invested', value: formatInr(total) },
        { label: 'Gain', value: formatInr(sipFv - total) },
        { label: 'How', value: `${formatInr(monthly)}/mo` },
      ],
    },
  ];

  const verdict = (
    <>
      For your inputs, the lumpsum ends about{' '}
      <strong className="font-semibold text-ink">{formatInr(gap)}</strong>{' '}
      {lumpWins ? 'higher' : 'lower'} than the SIP — the lump is invested
      longer, so it usually{' '}
      {lumpWins
        ? 'wins when returns are steadily positive'
        : 'falls short when monthly averaging catches market dips'}
      ; an SIP wins when the market dips early then recovers.{' '}
      <em className="not-italic text-ink-muted">
        Based on your assumptions — not a recommendation.
      </em>
    </>
  );

  const caveats = [
    'Neither outcome is guaranteed — a lumpsum wins in steadily rising markets; an SIP softens the risk of a bad entry point.',
    'This is only a fair comparison when you already hold the full amount today. Most people run an SIP from monthly income they don\'t have upfront.',
    'Returns are your assumption — try 8%, 10% and 12% to see how the gap moves.',
  ];

  // ponytail: caveats with apostrophes in JS string literals are fine; only JSX text nodes need escaping
  const excelTable: ExcelTable = {
    summary: `${config.name} — ${formatInrShort(total)} over ${years} yr${years === 1 ? '' : 's'} at ${rate}% assumed return.`,
    note: 'Educational illustration only — not investment advice. Returns are your own assumption; real markets vary.',
    headers: ['Option', 'Final Value'],
    rows: [
      ['Lumpsum final', Math.round(lumpFv)],
      ['SIP final', Math.round(sipFv)],
    ],
    colFormats: ['text', 'inr'],
  };

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* ── Left: inputs ── */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Numbers</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          The same money invested either way — all at once, or spread monthly.
        </p>

        <RangeField
          label="Total Amount"
          tip="The same money invested either way"
          value={total}
          min={50_000}
          max={100_000_000}
          step={50_000}
          format={formatInr}
          presets={[
            { label: '₹6L', value: 600_000 },
            { label: '₹12L', value: 1_200_000 },
            { label: '₹25L', value: 2_500_000 },
            { label: '₹50L', value: 5_000_000 },
          ]}
          onChange={setTotal}
          unit="₹"
        />

        <RangeField
          label="Years"
          tip="Investment period"
          value={years}
          min={1}
          max={40}
          step={1}
          format={(n) => `${n} ${n === 1 ? 'yr' : 'yrs'}`}
          presets={[
            { label: '5 yrs', value: 5 },
            { label: '10 yrs', value: 10 },
            { label: '15 yrs', value: 15 },
            { label: '20 yrs', value: 20 },
          ]}
          onChange={setYears}
          unit="yrs"
        />

        <RangeField
          label="Assumed Return"
          tip="Your assumption, not our prediction"
          value={rate}
          min={1}
          max={30}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[
            { label: '8%', value: 8 },
            { label: '10%', value: 10 },
            { label: '12%', value: 12 },
            { label: '15%', value: 15 },
          ]}
          onChange={setRate}
          unit="%"
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{ total, years, rate }} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      {/* ── Right: results ── */}
      <div ref={resultRef}>
        <VersusLayout options={options} verdict={verdict} caveats={caveats} />

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard
              text={`**The lumpsum has more time in the market.** At ${rate}% assumed return, ${formatInrShort(total)} invested today grows for the full ${years} ${years === 1 ? 'year' : 'years'} — every month an SIP waits, that month's share earns less.`}
            />
            <AiCard
              text={`**An SIP smooths your entry point.** Investing ${formatInr(monthly)}/mo means you buy at different prices each month — when markets dip early, you accumulate more units and can recover faster than a lumpsum placed at a peak.`}
            />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. Returns are your own assumption; real markets vary." />
          </div>
        </Section>

        {related.length > 0 && (
          <Section>
            <SectionHeader index="✦" title="Related Calculators" />
            <div className="flex gap-3 overflow-x-auto pb-1 sm:grid sm:grid-cols-2 sm:overflow-visible lg:grid-cols-4">
              {related.map((c) => (
                <RelatedCard key={c.slug} emoji={c.emoji} name={c.name} desc={c.sub} accent="royal" href={`/calculators/${c.slug}`} />
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

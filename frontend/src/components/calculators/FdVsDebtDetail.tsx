'use client';

/**
 * FdVsDebtDetail — 'fd-vs-debt' view: side-by-side post-tax comparison of
 * a Fixed Deposit and a Debt Mutual Fund for the same lump-sum and assumed rate.
 *
 * Since April 2023, debt-fund gains are taxed at slab — just like FD interest.
 * Both sides carry the same tax treatment here; the only mechanical difference
 * in this model is compounding frequency (FD quarterly, debt fund annual).
 *
 * COMPLIANCE: educational estimate on the user&#39;s own figures — not investment
 * or tax advice. FD is DICGC-insured; a debt fund is a market product and can
 * lose value — different risk profiles, not comparable on return alone.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeFd, formatInr } from '@/lib/finance';
import { computeSip } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';
import { VersusLayout, type VsOption } from './VersusLayout';

// ── Local slab select (same pattern as DividendTaxDetail) ────────────────────
const SLABS = [5, 10, 15, 20, 30];

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="mb-4 block">
      <span className="mb-1.5 block text-small font-semibold text-ink">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────
export function FdVsDebtDetail({ config }: { config: CalcConfig }) {
  const [amount, setAmount] = React.useState(500000);
  const [rate, setRate] = React.useState(7);
  const [years, setYears] = React.useState(5);
  const [slabPct, setSlabPct] = React.useState(30);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const { fdNet, fdTax, fdMaturity, debtNet, debtTax, debtVal, fdWins } =
    React.useMemo(() => {
      const fd = computeFd(amount, rate, years); // quarterly compounding
      const fdGain = Math.max(fd.maturity - amount, 0);
      const fdTaxAmt = fdGain * (slabPct / 100) * 1.04;
      const fdNetAmt = fd.maturity - fdTaxAmt;

      const debt = computeSip({ monthlySip: 0, lumpSum: amount, years, annualRatePct: rate });
      const debtGain = Math.max(debt.futureValue - amount, 0);
      const debtTaxAmt = debtGain * (slabPct / 100) * 1.04;
      const debtNetAmt = debt.futureValue - debtTaxAmt;

      return {
        fdNet: fdNetAmt,
        fdTax: fdTaxAmt,
        fdMaturity: fd.maturity,
        debtNet: debtNetAmt,
        debtTax: debtTaxAmt,
        debtVal: debt.futureValue,
        fdWins: fdNetAmt >= debtNetAmt,
      };
    }, [amount, rate, years, slabPct]);

  const reset = () => {
    setAmount(500000);
    setRate(7);
    setYears(5);
    setSlabPct(30);
  };

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${formatInr(amount)} at ${rate}% for ${years} yr${years === 1 ? '' : 's'}, ${slabPct}% slab: FD after tax ${formatInr(Math.round(fdNet))}, Debt fund after tax ${formatInr(Math.round(debtNet))}.`,
    note: 'Educational estimate only — not investment or tax advice. Returns are user-assumed; a debt fund is a market product and can lose value. FD is DICGC-insured up to ₹5 L per bank.',
    headers: ['Option', 'After-tax value'],
    rows: [
      ['FD after tax', Math.round(fdNet)],
      ['Debt fund after tax', Math.round(debtNet)],
    ],
    colFormats: ['text', 'inr'],
  };

  const options: VsOption[] = [
    {
      label: 'Fixed Deposit',
      headline: formatInr(fdNet),
      headlineLabel: 'Value after tax',
      winner: fdWins,
      rows: [
        { label: 'Maturity (pre-tax)', value: formatInr(fdMaturity) },
        { label: 'Tax at slab', value: formatInr(fdTax) },
        { label: 'Compounding', value: 'Quarterly' },
      ],
    },
    {
      label: 'Debt Fund',
      headline: formatInr(debtNet),
      headlineLabel: 'Value after tax',
      winner: !fdWins,
      rows: [
        { label: 'Value (pre-tax)', value: formatInr(debtVal) },
        { label: 'Tax at slab', value: formatInr(debtTax) },
        { label: 'Compounding', value: 'Annual (assumed)' },
      ],
    },
  ];

  const diff = Math.abs(fdNet - debtNet);
  const verdict = `At the same ${rate}% and your ${slabPct}% slab, the FD ends about ${formatInr(diff)} ${fdWins ? 'higher' : 'lower'} after tax — mostly because the FD compounds quarterly here. Both are now taxed the same way. Based on your inputs — not a recommendation.`;

  const caveats = [
    'Since April 2023, debt-fund gains are taxed at your slab — just like FD interest. We compare both AFTER tax.',
    'An FD has DICGC cover up to ₹5 L per bank; a debt fund carries market, credit and duration risk — different risk, not comparable on return alone.',
    'A debt fund is taxed only when you redeem; FD interest is taxed every year even if you don’t withdraw it — a real difference this simple compare leaves out.',
  ];

  const yrsFormat = (n: number) => `${n} ${n === 1 ? 'yr' : 'yrs'}`;

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      {/* ── Left: inputs ── */}
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Comparison</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          Same amount, same rate — see what changes after tax.
        </p>

        <RangeField
          label="Amount"
          tip="Invested once in each"
          value={amount}
          min={10000}
          max={100000000}
          step={10000}
          format={formatInr}
          presets={[
            { label: '₹1L', value: 100000 },
            { label: '₹5L', value: 500000 },
            { label: '₹10L', value: 1000000 },
            { label: '₹25L', value: 2500000 },
          ]}
          onChange={setAmount}
          unit="₹"
        />

        <RangeField
          label="Assumed Return"
          tip="Same rate for both — your assumption"
          value={rate}
          min={1}
          max={15}
          step={0.25}
          format={(n) => `${n}%`}
          presets={[
            { label: '6%', value: 6 },
            { label: '7%', value: 7 },
            { label: '7.5%', value: 7.5 },
            { label: '8%', value: 8 },
          ]}
          onChange={setRate}
          unit="%"
        />

        <RangeField
          label="Years"
          tip="How long invested"
          value={years}
          min={1}
          max={30}
          step={1}
          format={yrsFormat}
          presets={[
            { label: '3 yrs', value: 3 },
            { label: '5 yrs', value: 5 },
            { label: '10 yrs', value: 10 },
            { label: '15 yrs', value: 15 },
          ]}
          onChange={setYears}
          unit="yrs"
        />

        <Select
          label="Your income-tax slab"
          value={String(slabPct)}
          onChange={(v) => setSlabPct(Number(v))}
          options={SLABS.map((s) => ({ value: String(s), label: `${s}%` }))}
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>Reset</Btn>
          <ResultActions vals={{}} name={config.name} targetRef={resultRef} table={excelTable} />
        </div>
      </Panel>

      {/* ── Right: results ── */}
      <div ref={resultRef}>
        <VersusLayout options={options} verdict={verdict} caveats={caveats} />

        <Section className="mt-3.5">
          <SectionHeader index="✶" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text="**Tax parity since April 2023** — debt fund gains are now taxed at your income-tax slab, exactly like FD interest. The old long-term indexation benefit is gone, so the tax difference between these two is now zero." />
            <AiCard text="**Compounding frequency is the only edge here** — the FD compounds quarterly while the debt-fund model uses annual compounding. Over longer horizons that quarterly edge can widen the gap noticeably, even at the same stated rate." />
          </div>
          <div className="mt-3">
            <SoWhat>
              The main question is <b className="font-semibold text-ink">risk vs guarantee</b>, not tax. An FD locks in the rate and is insured. A debt fund can deliver more — or less — and has no guarantee.
            </SoWhat>
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment advice. Returns are your assumption; a debt fund’s value can move and is not guaranteed like an FD." />
          </div>
        </Section>

        {related.length > 0 && (
          <Section>
            <SectionHeader index="✶" title="Related Calculators" />
            <div className="flex gap-3 overflow-x-auto pb-1 sm:grid sm:grid-cols-2 sm:overflow-visible lg:grid-cols-4">
              {related.map((c) => (
                <RelatedCard
                  key={c.slug}
                  emoji={c.emoji}
                  name={c.name}
                  desc={c.sub}
                  accent="royal"
                  href={`/calculators/${c.slug}`}
                />
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

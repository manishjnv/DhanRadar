'use client';

/**
 * RentVsBuyDetail — 'rent-vs-buy' view (Versus): compare NET WORTH at a holding
 * horizon between (a) buying with a home loan and (b) renting + investing the
 * difference (down payment + monthly EMI surplus).
 *
 * Property appreciation is the dominant swing factor — we compute base, low
 * (appr−3%) and high (appr+3%) cases and surface all three in the verdict so
 * the user sees a range, not a false single answer.
 *
 * COMPLIANCE: factual on the user's own figures; educational only; no advisory
 * verbs as advice; no numeric DhanRadar scores in DOM; winner only "for your
 * inputs".
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, RangeField, AiCard, RelatedCard } from './ui';
import { computeLoan, computeSip, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';
import { VersusLayout, type VsOption } from './VersusLayout';

// Compute buyer net worth and renter net worth at a given appreciation rate.
function netWorths(
  price: number,
  dpPct: number,
  loanRate: number,
  tenure: number,
  rent: number,
  investReturn: number,
  appr: number,
  horizon: number,
): { buyerNet: number; renterNet: number; propValue: number; outstanding: number; emi: number; downPayment: number; monthlySurplus: number } {
  const downPayment = price * dpPct / 100;
  const loanAmt = price - downPayment;
  const loan = computeLoan({ principal: loanAmt, annualRatePct: loanRate, years: tenure });
  const emi = loan.emi;
  const horizonYrs = Math.min(horizon, tenure);
  const propValue = price * Math.pow(1 + appr / 100, horizon);
  // Find outstanding balance at the horizon year from the amortization series.
  const yp = loan.series.find((p) => p.year === horizonYrs);
  const outstanding = yp ? yp.balance : (horizon >= tenure ? 0 : loanAmt);
  const buyerNet = propValue - outstanding;
  // Renter invests the down payment as lump sum + monthly (EMI − rent) surplus.
  const monthlySurplus = Math.max(emi - rent, 0);
  const renterNet = computeSip({
    monthlySip: monthlySurplus,
    lumpSum: downPayment,
    years: horizon,
    annualRatePct: investReturn,
  }).futureValue;
  return { buyerNet, renterNet, propValue, outstanding, emi, downPayment, monthlySurplus };
}

export function RentVsBuyDetail({ config }: { config: CalcConfig }) {
  const [price, setPrice] = React.useState(10_000_000);
  const [dpPct, setDpPct] = React.useState(20);
  const [loanRate, setLoanRate] = React.useState(8.5);
  const [tenure, setTenure] = React.useState(20);
  const [rent, setRent] = React.useState(30_000);
  const [investReturn, setInvestReturn] = React.useState(12);
  const [appr, setAppr] = React.useState(6);
  const [horizon, setHorizon] = React.useState(10);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const reset = () => {
    setPrice(10_000_000); setDpPct(20); setLoanRate(8.5); setTenure(20);
    setRent(30_000); setInvestReturn(12); setAppr(6); setHorizon(10);
  };

  const calc = React.useMemo(() => {
    const base = netWorths(price, dpPct, loanRate, tenure, rent, investReturn, appr, horizon);
    const apprLow = Math.max(appr - 3, 0);
    const low = netWorths(price, dpPct, loanRate, tenure, rent, investReturn, apprLow, horizon);
    const high = netWorths(price, dpPct, loanRate, tenure, rent, investReturn, appr + 3, horizon);
    return { base, low, high, apprLow };
  }, [price, dpPct, loanRate, tenure, rent, investReturn, appr, horizon]);

  const { base, low, high, apprLow } = calc;
  const buyWinsBase = base.buyerNet >= base.renterNet;

  const options: VsOption[] = [
    {
      label: 'Buy a Home',
      headline: formatInr(base.buyerNet),
      headlineLabel: 'Net worth at horizon',
      winner: buyWinsBase,
      rows: [
        { label: 'Property value', value: formatInr(base.propValue) },
        { label: 'Loan left', value: formatInr(base.outstanding) },
        { label: 'EMI', value: `${formatInr(base.emi)}/mo` },
      ],
    },
    {
      label: 'Rent + Invest',
      headline: formatInr(base.renterNet),
      headlineLabel: 'Net worth at horizon',
      winner: !buyWinsBase,
      rows: [
        { label: 'Invested upfront', value: formatInr(base.downPayment) },
        { label: 'Monthly invested', value: `${formatInr(base.monthlySurplus)}/mo` },
        { label: 'Rent', value: `${formatInr(rent)}/mo` },
      ],
    },
  ];

  const verdict = (
    <>
      At {appr}% appreciation,{' '}
      <strong className="font-semibold text-ink">
        {buyWinsBase ? 'buying' : 'renting + investing'}
      </strong>{' '}
      ends about{' '}
      <strong className="font-semibold text-ink">
        {formatInr(Math.abs(base.buyerNet - base.renterNet))}
      </strong>{' '}
      ahead. But this flips with appreciation — at {apprLow}% buying gives{' '}
      {formatInr(low.buyerNet)} vs renting {formatInr(low.renterNet)}, and at{' '}
      {appr + 3}% buying gives {formatInr(high.buyerNet)} vs{' '}
      {formatInr(high.renterNet)}.{' '}
      <em className="not-italic text-ink-muted">
        The honest answer is a range, not one verdict.
      </em>
    </>
  );

  const caveats = [
    'Property appreciation is the biggest swing — a couple of percent either way can flip the result. We show your rate plus a ±3% range.',
    'This ignores stamp duty, registration, brokerage, maintenance and property tax — all real costs of buying.',
    'Owning a home has a stability and emotional value this calculation cannot capture; renting keeps you flexible.',
  ];

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${formatInr(price)} property, ${dpPct}% down, ${loanRate}% loan, ${horizon}-yr horizon, ${appr}% appreciation.`,
    note: 'Educational illustration only — not investment or property advice. The outcome depends heavily on assumptions (appreciation, return, rent) that real life will not match exactly.',
    headers: ['Option', 'Net Worth at Horizon'],
    rows: [
      ['Buy net worth', Math.round(base.buyerNet)],
      ['Rent+Invest net worth', Math.round(base.renterNet)],
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
          Compare net worth at your horizon — buying a home versus renting and investing the difference.
        </p>

        <RangeField
          label="Property Price"
          tip="Today's price of the home"
          value={price}
          min={1_000_000}
          max={200_000_000}
          step={100_000}
          format={formatInr}
          presets={[
            { label: '₹75L', value: 7_500_000 },
            { label: '₹1Cr', value: 10_000_000 },
            { label: '₹2Cr', value: 20_000_000 },
          ]}
          onChange={setPrice}
          unit="₹"
        />

        <RangeField
          label="Down Payment %"
          tip="Paid upfront from your pocket"
          value={dpPct}
          min={5}
          max={60}
          step={1}
          format={(n) => `${n}%`}
          presets={[
            { label: '10%', value: 10 },
            { label: '20%', value: 20 },
            { label: '30%', value: 30 },
          ]}
          onChange={setDpPct}
          unit="%"
        />

        <RangeField
          label="Loan Rate"
          tip="Home-loan interest rate"
          value={loanRate}
          min={5}
          max={15}
          step={0.25}
          format={(n) => `${n}%`}
          presets={[
            { label: '8%', value: 8 },
            { label: '8.5%', value: 8.5 },
            { label: '9%', value: 9 },
          ]}
          onChange={setLoanRate}
          unit="%"
        />

        <RangeField
          label="Loan Tenure"
          tip="Loan repayment period"
          value={tenure}
          min={5}
          max={30}
          step={1}
          format={(n) => `${n} yrs`}
          presets={[
            { label: '15 yrs', value: 15 },
            { label: '20 yrs', value: 20 },
            { label: '25 yrs', value: 25 },
          ]}
          onChange={setTenure}
          unit="yrs"
        />

        <RangeField
          label="Monthly Rent"
          tip="Rent for a similar home today"
          value={rent}
          min={5_000}
          max={1_000_000}
          step={1_000}
          format={formatInr}
          presets={[
            { label: '₹20K', value: 20_000 },
            { label: '₹30K', value: 30_000 },
            { label: '₹50K', value: 50_000 },
          ]}
          onChange={setRent}
          unit="₹"
        />

        <RangeField
          label="Investment Return"
          tip="If a renter invests the difference — your assumption"
          value={investReturn}
          min={1}
          max={30}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[
            { label: '10%', value: 10 },
            { label: '12%', value: 12 },
            { label: '15%', value: 15 },
          ]}
          onChange={setInvestReturn}
          unit="%"
        />

        <RangeField
          label="Property Appreciation"
          tip="How fast the home's price rises (the swing factor)"
          value={appr}
          min={0}
          max={15}
          step={0.5}
          format={(n) => `${n}%`}
          presets={[
            { label: '3%', value: 3 },
            { label: '6%', value: 6 },
            { label: '9%', value: 9 },
          ]}
          onChange={setAppr}
          unit="%"
        />

        <RangeField
          label="Horizon"
          tip="How long before you'd sell / move"
          value={horizon}
          min={1}
          max={30}
          step={1}
          format={(n) => `${n} yrs`}
          presets={[
            { label: '7 yrs', value: 7 },
            { label: '10 yrs', value: 10 },
            { label: '15 yrs', value: 15 },
          ]}
          onChange={setHorizon}
          unit="yrs"
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
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard
              text={`**Appreciation is the biggest swing factor.** At ${appr}% the buyer ends ${formatInr(base.buyerNet)}, but drop it to ${apprLow}% and that shifts to ${formatInr(low.buyerNet)} — a difference of ${formatInr(Math.abs(base.buyerNet - low.buyerNet))}. Before deciding, try a low-appreciation scenario and see if you are still comfortable.`}
            />
            <AiCard
              text={`**The renter invests the surplus.** The down payment of ${formatInr(base.downPayment)} goes into the market at ${investReturn}% assumed return, plus ${formatInr(base.monthlySurplus)}/mo if the EMI exceeds the rent. If rent is higher than the EMI, the renter invests only the lump sum — and the buyer has a natural edge.`}
            />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not investment or property advice. The outcome depends heavily on assumptions (appreciation, return, rent) that real life will not match exactly." />
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

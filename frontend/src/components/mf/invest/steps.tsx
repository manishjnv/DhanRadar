/**
 * InvestWizard — step panes (Step1..Step6).
 *
 * Pulled out of InvestWizard.tsx purely to keep that file under control —
 * every component here is pure render, driven entirely by props. State and
 * BSE call sites stay in InvestWizard.tsx; shared primitives + BSE wire
 * helpers live in parts.tsx.
 */
'use client';

import * as React from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import {
  Chip,
  ChipRow,
  GrowthBars,
  MeansForYouCallout,
  NotificationsPreview,
  PaymentMethodRow,
  ProjectionTrio,
  ReferenceStatesDetails,
  SmartSuggestionsGrid,
  TimelineItem,
  VerificationRow,
  STEP4_FAILURE_STATES,
  STEP2_REFERENCE_STATES,
  DEMO_UCC,
  UCC_FIELDS,
  STAGE_DEFS,
  matchesStage,
  toneFromUccValue,
  uccField,
  formatINR,
  formatINRLakh,
  ordinalSuffix,
  type BseWebhookEvent,
  type FundHeadExt,
  type UccStatusObject,
} from './parts';

// ===========================================================================
// Step 1 — Investment details
// ===========================================================================
export function Step1({
  fund,
  investType,
  setInvestType,
  amount,
  setAmount,
  effectiveMin,
  amountValid,
  schemeLoading,
  schemeError,
  sessionActive,
  projection,
  growthSeries,
  durationYears,
}: {
  fund: FundHeadExt;
  investType: 'sip' | 'lumpsum';
  setInvestType: (t: 'sip' | 'lumpsum') => void;
  amount: number;
  setAmount: (n: number) => void;
  effectiveMin: number | null;
  amountValid: boolean;
  schemeLoading: boolean;
  schemeError: string | null;
  sessionActive: boolean | null;
  projection: { conservative: number; expected: number; optimistic: number; invested: number };
  growthSeries: number[];
  durationYears: number;
}) {
  const chips = [1000, 2500, 5000, 10000, 25000];
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>How do you want to invest?</CardTitle>
          <ChipRow kinds={['live', 'uat']} />
        </CardHeader>
        <CardBody>
          {sessionActive === false && (
            <p className="mb-3 text-small text-amber">
              BSE UAT session is not active — log in above to look up this fund&apos;s scheme code and
              minimum amount.
            </p>
          )}
          {schemeLoading && <p className="mb-3 text-small text-ink-muted">Looking up scheme…</p>}
          {schemeError && <p className="mb-3 text-small text-red">{schemeError}</p>}

          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => setInvestType('sip')}
              className={`rounded-md border p-3.5 text-left ${investType === 'sip' ? 'border-royal bg-royal/5' : 'border-line'}`}
            >
              <div className="flex items-center gap-2 text-small font-semibold text-ink">
                Monthly SIP <Chip kind="preview" />
                <span className="ml-auto rounded bg-emerald/10 px-1.5 py-0.5 text-micro font-semibold text-emerald">
                  Rupee-cost averaging
                </span>
              </div>
              <p className="mt-1 text-caption text-ink-secondary">
                Invest a fixed amount every month. Smooths out market ups and downs.
              </p>
            </button>
            <button
              type="button"
              onClick={() => setInvestType('lumpsum')}
              className={`rounded-md border p-3.5 text-left ${investType === 'lumpsum' ? 'border-royal bg-royal/5' : 'border-line'}`}
            >
              <div className="flex items-center gap-2 text-small font-semibold text-ink">
                One-time Lumpsum <Chip kind="uat" />
              </div>
              <p className="mt-1 text-caption text-ink-secondary">
                Invest a single amount now. Live end-to-end via BSE UAT.
              </p>
            </button>
          </div>

          <div className="mt-4 rounded-md border border-line bg-surface p-4">
            <div className="flex items-center gap-2">
              <span className="text-h2 font-medium text-ink-faint">₹</span>
              <input
                inputMode="numeric"
                aria-label="Investment amount"
                value={amount.toLocaleString('en-IN')}
                onChange={(e) => {
                  const n = Number(e.target.value.replace(/[^\d]/g, ''));
                  setAmount(Number.isNaN(n) ? 0 : n);
                }}
                className="w-full border-0 bg-transparent text-h1 font-medium text-ink outline-none"
              />
              {investType === 'sip' && (
                <span className="shrink-0 rounded-md bg-royal/5 px-2 py-1 text-caption font-medium text-royal">
                  per month
                </span>
              )}
            </div>
            <input
              type="range"
              aria-label="Adjust amount"
              min={effectiveMin ?? 500}
              max={100000}
              step={500}
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
              className="mt-4 w-full accent-royal"
            />
            <div className="mt-2.5 flex justify-between text-caption text-ink-faint">
              <span>Minimum {effectiveMin != null ? formatINR(effectiveMin) : '—'}</span>
              <span>Common starting point: ₹10,000</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {chips.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setAmount(c)}
                  className={`rounded-full border px-3 py-1.5 text-caption font-semibold ${amount === c ? 'border-navy bg-navy text-white' : 'border-line text-ink-secondary'}`}
                >
                  {formatINR(c)}
                </button>
              ))}
            </div>
            {!amountValid && (
              <p className="mt-2 text-caption text-red">
                Amount is below the minimum of {formatINR(effectiveMin)}.
              </p>
            )}
          </div>

          <MeansForYouCallout>
            {investType === 'sip' ? (
              <>
                {formatINR(amount)} a month for {durationYears} years puts about{' '}
                {formatINRLakh(amount * 12 * durationYears)} of your own money in, and could grow to
                roughly {formatINRLakh(projection.expected)} at a 13% long-run average. Returns are not
                guaranteed — markets move.
              </>
            ) : (
              <>
                {formatINR(amount)} invested once could grow to roughly {formatINRLakh(projection.expected)}{' '}
                over {durationYears} years at a 13% long-run average. Returns are not guaranteed —
                markets move.
              </>
            )}
          </MeansForYouCallout>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Where this could land</CardTitle>
          <ChipRow kinds={['preview']} />
        </CardHeader>
        <CardBody>
          <p className="mb-3 text-caption text-ink-muted">
            Illustrative only — not a promise or advice. Client-side estimate at three growth rates.
          </p>
          <ProjectionTrio
            conservative={projection.conservative}
            expected={projection.expected}
            optimistic={projection.optimistic}
            investedLabel={(v) => `Gain ${formatINRLakh(v - projection.invested)}`}
          />
          <GrowthBars values={growthSeries} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Smart suggestions</CardTitle>
          <ChipRow kinds={['preview']} />
        </CardHeader>
        <CardBody>
          <SmartSuggestionsGrid />
        </CardBody>
      </Card>
    </>
  );
}

// ===========================================================================
// Step 2 — Verification
// ===========================================================================
export function Step2({
  uccLoading,
  uccError,
  uccStatus,
  uccStatusObject,
  onLoad,
  sessionActive,
}: {
  uccLoading: boolean;
  uccError: string | null;
  uccStatus: string | null;
  uccStatusObject: UccStatusObject | null;
  onLoad: () => void;
  sessionActive: boolean | null;
}) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Your investor profile</CardTitle>
          <div className="ml-auto flex items-center gap-2">
            <ChipRow kinds={['live', 'uat']} />
            <Button size="sm" onClick={onLoad} disabled={uccLoading || sessionActive === false}>
              {uccLoading ? 'Loading…' : 'Load investor profile'}
            </Button>
          </div>
        </CardHeader>
        <CardBody>
          {sessionActive === false && (
            <p className="mb-3 text-small text-amber">Log in to the BSE UAT session above first.</p>
          )}
          {uccError && <p className="mb-3 text-small text-red">{uccError}</p>}
          {uccStatus && (
            <p className="mb-3 text-small text-ink-secondary">
              UCC <span className="font-mono">{DEMO_UCC}</span> status:{' '}
              <span className="font-semibold text-ink">{uccStatus}</span>
            </p>
          )}
        </CardBody>
        {uccStatusObject ? (
          <div>
            {UCC_FIELDS.map((f) => {
              const isBank = f.key === 'bank_account';
              const tone = toneFromUccValue(uccField(uccStatusObject, f.key), isBank);
              const statusLabel = tone === 'ok' ? 'Verified' : tone === 'warn' ? 'Attention' : tone === 'bad' ? 'Failed' : 'Pending';
              return (
                <VerificationRow
                  key={f.key}
                  tone={tone}
                  name={f.name}
                  description={f.description}
                  statusLabel={statusLabel}
                  note={isBank && tone !== 'ok' ? 'BSE demo bank verification — open item with BSE.' : undefined}
                />
              );
            })}
            <VerificationRow tone="ok" name="Address & contact" description="On file with your registered contact details" statusLabel="Complete" preview />
            <VerificationRow tone="ok" name="Risk profile" description="Assessed during onboarding" statusLabel="On file" preview />
          </div>
        ) : (
          !uccLoading && <CardBody className="pt-0 text-small text-ink-muted">Load the profile to see verification status.</CardBody>
        )}
        <CardBody className="pt-0">
          <MeansForYouCallout>
            Nothing here blocks a lumpsum investment today. Bank verification is a known open item on
            the BSE demo environment and does not affect the lumpsum order flow.
          </MeansForYouCallout>
        </CardBody>
      </Card>

      <ReferenceStatesDetails summary="Empty & first-time states" states={STEP2_REFERENCE_STATES} />
    </>
  );
}

// ===========================================================================
// Step 3 — SIP setup (interactive UI, execution gated on BSE mandate)
// ===========================================================================
export function Step3({
  amount,
  setAmount,
  frequency,
  setFrequency,
  debitDate,
  setDebitDate,
  durationYears,
  setDurationYears,
  stepUpPct,
  setStepUpPct,
  stepUpOutcome,
  flatOutcome,
}: {
  amount: number;
  setAmount: (n: number) => void;
  frequency: 'monthly' | 'quarterly' | 'weekly';
  setFrequency: (f: 'monthly' | 'quarterly' | 'weekly') => void;
  debitDate: number;
  setDebitDate: (n: number) => void;
  durationYears: number;
  setDurationYears: (n: number) => void;
  stepUpPct: number;
  setStepUpPct: (n: number) => void;
  stepUpOutcome: { invested: number; corpus: number };
  flatOutcome: number;
}) {
  const gain = stepUpOutcome.corpus - stepUpOutcome.invested;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Set up your SIP</CardTitle>
        <ChipRow kinds={['preview']} />
      </CardHeader>
      <CardBody>
        <div className="rounded-md border border-amber/30 bg-amber/10 p-3 text-small text-ink-secondary">
          SIP execution awaits BSE mandate enablement (bank verification) — lumpsum is live end-to-end
          today. This step is fully interactive so you can preview a SIP plan.
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <div className="mb-1.5 text-caption font-semibold text-ink-secondary">SIP amount</div>
            <div className="flex items-center gap-2 rounded-md border border-line bg-surface p-2.5">
              <span className="text-h3 text-ink-faint">₹</span>
              <input
                inputMode="numeric"
                aria-label="SIP amount"
                value={amount.toLocaleString('en-IN')}
                onChange={(e) => {
                  const n = Number(e.target.value.replace(/[^\d]/g, ''));
                  setAmount(Number.isNaN(n) ? 0 : n);
                }}
                className="w-full border-0 bg-transparent text-h3 font-medium text-ink outline-none"
              />
            </div>
          </div>
          <div>
            <div className="mb-1.5 text-caption font-semibold text-ink-secondary">Frequency</div>
            <div className="flex gap-1.5">
              {(['monthly', 'quarterly', 'weekly'] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFrequency(f)}
                  className={`rounded-md border px-3 py-1.5 text-caption font-semibold ${frequency === f ? 'border-navy bg-navy text-white' : 'border-line text-ink-secondary'}`}
                >
                  {f[0].toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
            <div className="mb-1.5 mt-3 text-caption font-semibold text-ink-secondary">Debit date</div>
            <div className="flex flex-wrap gap-1.5">
              {[1, 5, 10, 15, 25].map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDebitDate(d)}
                  className={`rounded-full border px-3 py-1.5 text-caption font-semibold ${debitDate === d ? 'border-navy bg-navy text-white' : 'border-line text-ink-secondary'}`}
                >
                  {d}
                  {ordinalSuffix(d)}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-md border border-line p-3">
            <div className="text-caption text-ink-secondary">Duration</div>
            <input
              type="range"
              min={1}
              max={30}
              value={durationYears}
              onChange={(e) => setDurationYears(Number(e.target.value))}
              className="mt-2 w-full accent-royal"
            />
            <div className="mt-1 text-small font-medium text-ink">{durationYears} years</div>
          </div>
          <div className="rounded-md border border-line p-3">
            <div className="text-caption text-ink-secondary">Step-up SIP</div>
            <input
              type="range"
              min={0}
              max={25}
              value={stepUpPct}
              onChange={(e) => setStepUpPct(Number(e.target.value))}
              className="mt-2 w-full accent-royal"
            />
            <div className="mt-1 text-small font-medium text-ink">+{stepUpPct}% / yr</div>
          </div>
          <div className="rounded-md border border-line p-3">
            <div className="text-caption text-ink-secondary">Instalments</div>
            <div className="mt-1 text-small font-medium text-ink">{durationYears * 12} · monthly</div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-md border border-emerald/30 bg-emerald/10 p-3">
            <div className="text-caption text-ink-secondary">You will invest</div>
            <div className="mt-1 text-h3 font-medium text-ink">{formatINRLakh(stepUpOutcome.invested)}</div>
            <div className="text-caption text-ink-faint">With {stepUpPct}% annual step-up</div>
          </div>
          <div className="rounded-md border border-emerald/30 bg-emerald/10 p-3">
            <div className="text-caption text-ink-secondary">Estimated corpus</div>
            <div className="mt-1 text-h3 font-medium text-ink">{formatINRLakh(stepUpOutcome.corpus)}</div>
            <div className="text-caption text-ink-faint">At 13% long-run average</div>
          </div>
          <div className="rounded-md border border-emerald/30 bg-emerald/10 p-3">
            <div className="text-caption text-ink-secondary">Estimated gain</div>
            <div className="mt-1 text-h3 font-medium text-ink">{formatINRLakh(gain)}</div>
            <div className="text-caption text-ink-faint">
              {stepUpOutcome.corpus > 0 ? `${Math.round((gain / stepUpOutcome.corpus) * 100)}% of final value` : '—'}
            </div>
          </div>
        </div>

        <MeansForYouCallout>
          Stepping up {stepUpPct}% a year vs. a flat {formatINR(amount)} SIP changes your final corpus
          by about {formatINRLakh(Math.abs(stepUpOutcome.corpus - flatOutcome))}. You can pause or
          cancel any instalment free of charge once SIP execution is enabled.
        </MeansForYouCallout>
      </CardBody>
    </Card>
  );
}

// ===========================================================================
// Step 4 — Payment
// ===========================================================================
export function Step4({
  paymentMethod,
  setPaymentMethod,
  sessionActive,
}: {
  paymentMethod: 'upi';
  setPaymentMethod: (m: 'upi') => void;
  sessionActive: boolean | null;
}) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>How would you like to pay?</CardTitle>
        </CardHeader>
        <CardBody className="space-y-2.5">
          {sessionActive === false && (
            <p className="text-small text-amber">Log in to the BSE UAT session above to place a live order.</p>
          )}
          <PaymentMethodRow
            icon="▲"
            name="UPI"
            description="Approve in your UPI app · money leaves instantly"
            tag="Fastest"
            chips={['live', 'uat']}
            selected={paymentMethod === 'upi'}
            onClick={() => setPaymentMethod('upi')}
          />
          <PaymentMethodRow icon="🏦" name="Net banking" description="58 banks · redirected to your bank, back in one step" tag="2–3 min" chips={['preview']} selected={false} disabled />
          <PaymentMethodRow icon="🔁" name="NACH auto-debit" description="Uses your existing mandate · nothing to approve today" tag="Best for SIP" chips={['preview']} selected={false} disabled />
          <PaymentMethodRow icon="✎" name="New e-mandate" description="One-time bank approval for all future SIP instalments" tag="1–2 days" chips={['preview']} selected={false} disabled />
          <PaymentMethodRow icon="↗" name="Bank transfer / NEFT" description="Transfer manually using the account details we generate" tag="Same day" chips={['preview']} selected={false} disabled />

          <div className="!mt-4 flex gap-3 rounded-md border border-royal/20 bg-royal/5 p-3">
            <span className="text-body">🔒</span>
            <div>
              <div className="text-caption font-semibold uppercase tracking-wide text-royal">How your money moves</div>
              <p className="mt-0.5 text-small leading-relaxed text-ink-secondary">
                Money goes directly to the exchange&apos;s clearing corporation (ICCL) — DhanRadar never
                holds funds. Pay before 3:00 PM on a business day and you get today&apos;s NAV; after
                that, the next business day&apos;s.
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>What happens after you pay</CardTitle>
          <ChipRow kinds={['preview']} />
        </CardHeader>
        <CardBody>
          <TimelineItem state="pending" name="Payment authorised" description="Instant with UPI" time="T+0" />
          <TimelineItem state="pending" name="Order sent to AMC" description="Cut-off 3:00 PM on business days" time="T+0" />
          <TimelineItem state="pending" name="NAV applied & units allotted" description="Units appear in your portfolio" time="T+1 business day" />
          <TimelineItem state="pending" name="Statement issued" description="Emailed by the AMC and stored in DhanRadar" time="T+2 business days" last />
        </CardBody>
      </Card>

      <ReferenceStatesDetails summary="Payment & network failure states" states={STEP4_FAILURE_STATES} />
    </>
  );
}

// ===========================================================================
// Step 5 — Review & confirm
// ===========================================================================
export function Step5({
  fund,
  isin,
  investType,
  amount,
  frequency,
  debitDate,
  schemeCode,
  consent,
  setConsent,
  orderError,
  isLumpsum,
  sessionActive,
  amountValid,
}: {
  fund: FundHeadExt;
  isin: string;
  investType: 'sip' | 'lumpsum';
  amount: number;
  frequency: string;
  debitDate: number;
  schemeCode: string | null;
  consent: boolean;
  setConsent: (b: boolean) => void;
  orderError: string | null;
  isLumpsum: boolean;
  sessionActive: boolean | null;
  amountValid: boolean;
}) {
  const rows: [string, React.ReactNode][] = [
    ['Fund', fund.fund_name_short || fund.scheme_name],
    ['ISIN', isin],
    ['AMC', fund.amc_name ?? '—'],
    ['Investment type', investType === 'sip' ? 'Monthly SIP (preview)' : 'One-time lumpsum'],
    ['Amount', investType === 'sip' ? `${formatINR(amount)} per month · ${debitDate}${ordinalSuffix(debitDate)} of month, ${frequency}` : formatINR(amount)],
    ['BSE scheme code', schemeCode ?? '— (session/scheme lookup pending)'],
    ['UCC (BSE UAT demo)', DEMO_UCC],
    ['Payment method', 'UPI'],
    ['Charges', 'Commission ₹0 (direct plan) · Transaction fee ₹0 · Stamp duty 0.005%'],
    ['Annual fund cost', fund.expense_ratio_pct != null ? `${fund.expense_ratio_pct.toFixed(2)}% of your holding, taken inside the NAV` : '—'],
    ['Exit load', fund.exit_load_pct != null ? `${fund.exit_load_pct}% if redeemed within ${fund.exit_load_days ?? '—'} days, nil after` : '—'],
    ['Risk level', fund.risk_o_meter ?? '—'],
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Check and confirm</CardTitle>
        <ChipRow kinds={isLumpsum ? ['live', 'uat'] : ['preview']} />
      </CardHeader>
      <div>
        {rows.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[160px_1fr] gap-3 border-b border-line px-6 py-2.5 text-small last:border-b-0">
            <span className="font-medium text-ink-muted">{k}</span>
            <span className="font-medium text-ink">{v}</span>
          </div>
        ))}
      </div>
      <CardBody>
        <div className="rounded-md border border-amber/30 bg-amber/10 p-3">
          <div className="text-caption font-semibold uppercase tracking-wide text-amber">Please read before confirming</div>
          <p className="mt-1 text-small text-ink-secondary">
            Mutual fund investments are subject to market risk. Read all scheme-related documents
            carefully. Past performance does not indicate future results. DhanRadar is an
            AMFI-registered Mutual Fund Distributor · ARN and earns no commission on direct plans.
            This is educational information, not investment advice.
          </p>
        </div>
        <label className="mt-3 flex items-start gap-2.5 text-small text-ink-secondary">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5 h-4 w-4 accent-royal"
          />
          <span>
            I have read the Scheme Information Document and understand the risks. I confirm this
            money is my own and legitimately sourced.
          </span>
        </label>
        {!isLumpsum && (
          <p className="mt-3 text-small text-ink-muted">
            SIP order placement is gated on BSE mandate enablement — switch to lumpsum in step 1 to
            place a live order today.
          </p>
        )}
        {isLumpsum && sessionActive === false && (
          <p className="mt-3 text-small text-amber">Log in to the BSE UAT session to place a live order.</p>
        )}
        {isLumpsum && !amountValid && <p className="mt-3 text-small text-red">Amount is below the fund&apos;s minimum.</p>}
        {orderError && (
          <div className="mt-3 rounded-md border border-red/30 bg-red/5 p-3 text-small text-red">{orderError}</div>
        )}
      </CardBody>
    </Card>
  );
}

// ===========================================================================
// Step 6 — Done (progressive: approve -> pay -> track)
// ===========================================================================
export function Step6({
  orderId,
  fund,
  amount,
  otp,
  setOtp,
  otpSending,
  otpSent,
  otpError,
  onStartApproval,
  approving,
  approved,
  approveError,
  onVerifyApproval,
  pgLoading,
  pgError,
  onOpenPgLink,
  events,
}: {
  orderId: string | null;
  fund: FundHeadExt;
  amount: number;
  otp: string;
  setOtp: (s: string) => void;
  otpSending: boolean;
  otpSent: boolean;
  otpError: string | null;
  onStartApproval: () => void;
  approving: boolean;
  approved: boolean;
  approveError: string | null;
  onVerifyApproval: () => void;
  pgLoading: boolean;
  pgError: string | null;
  onOpenPgLink: () => void;
  events: BseWebhookEvent[];
}) {
  if (!orderId) {
    return (
      <Card>
        <CardBody>
          <p className="text-small text-ink-muted">No order placed yet — go back to step 5 to confirm.</p>
        </CardBody>
      </Card>
    );
  }

  const reachedIndex = STAGE_DEFS.reduce((acc, s, i) => (events.some((e) => matchesStage(e, s.key)) ? i : acc), -1);

  return (
    <>
      <Card>
        <CardHeader>
          <div>
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald/10 text-h2 text-emerald">✓</span>
          </div>
          <div>
            <CardTitle>Your order is placed</CardTitle>
            <p className="text-small text-ink-muted">Order {orderId} · {formatINR(amount)}</p>
          </div>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>1 · Approve your order</CardTitle>
          <ChipRow kinds={['live', 'uat']} />
        </CardHeader>
        <CardBody className="space-y-3">
          {!approved ? (
            <>
              <p className="text-small text-ink-secondary">
                Order <span className="font-mono">{orderId}</span> needs OTP approval before it moves
                forward.
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" onClick={onStartApproval} disabled={otpSending}>
                  {otpSending ? 'Sending…' : otpSent ? 'Resend OTP' : 'Send OTP'}
                </Button>
                {otpSent && <span className="text-caption text-emerald">OTP sent to the UCC&apos;s registered contact.</span>}
              </div>
              {otpError && <p className="text-small text-red">{otpError}</p>}
              {otpSent && (
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    placeholder="6-digit OTP"
                    className="w-40"
                  />
                  <Button size="sm" onClick={onVerifyApproval} disabled={approving || !otp}>
                    {approving ? 'Approving…' : 'Approve order'}
                  </Button>
                </div>
              )}
              {approveError && <p className="text-small text-red">{approveError}</p>}
            </>
          ) : (
            <p className="text-small text-emerald">Order approved.</p>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2 · Complete payment</CardTitle>
          <ChipRow kinds={['live', 'uat']} />
        </CardHeader>
        <CardBody className="space-y-2">
          <Button size="sm" onClick={onOpenPgLink} disabled={pgLoading}>
            {pgLoading ? 'Fetching…' : 'Open BSE payment page'}
          </Button>
          <p className="text-caption text-ink-muted">
            Opens in a new tab — final UPI settlement runs on BSE / Razorpay&apos;s own page.
          </p>
          {pgError && <p className="text-small text-red">{pgError}</p>}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3 · Track this transaction</CardTitle>
          <ChipRow kinds={['live', 'uat']} />
        </CardHeader>
        <CardBody>
          {STAGE_DEFS.map((s, i) => (
            <TimelineItem
              key={s.key}
              state={i < reachedIndex ? 'done' : i === reachedIndex ? 'on' : 'pending'}
              name={s.name}
              description=""
              last={i === STAGE_DEFS.length - 1}
            />
          ))}
        </CardBody>
        <div className="border-t border-line">
          {events.length === 0 ? (
            <p className="p-4 text-small text-ink-muted">No webhook events yet — polling every 5 seconds.</p>
          ) : (
            <div className="overflow-x-auto p-4">
              <table className="w-full text-left text-caption">
                <thead>
                  <tr className="border-b border-line text-ink-muted">
                    <th className="py-1.5 pr-3">Event</th>
                    <th className="py-1.5 pr-3">Client</th>
                    <th className="py-1.5 pr-3">Received</th>
                    <th className="py-1.5">Processed</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e, i) => (
                    <tr key={i} className="border-b border-line/50">
                      <td className="py-1 pr-3 font-mono">{e.event || e.event_type}</td>
                      <td className="py-1 pr-3">{e.client_code ?? '—'}</td>
                      <td className="py-1 pr-3 whitespace-nowrap">{e.received_at ? new Date(e.received_at).toLocaleString() : '—'}</td>
                      <td className="py-1 whitespace-nowrap">{e.processed_at ? new Date(e.processed_at).toLocaleString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Units expected / NAV applied</CardTitle>
          <ChipRow kinds={['preview']} />
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ['Units expected', fund.nav_latest ? `~${(amount / fund.nav_latest).toFixed(2)}` : '—'],
            ['NAV applied', fund.nav_latest != null ? `₹${fund.nav_latest}` : '—'],
            ['Units allotted by', 'T+1 business day'],
            ['Statement issued', 'T+2 business days'],
          ].map(([l, v]) => (
            <div key={l}>
              <div className="text-caption text-ink-faint">{l}</div>
              <div className="text-small font-medium text-ink">{v}</div>
            </div>
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notifications you&apos;ll get</CardTitle>
          <ChipRow kinds={['preview']} />
        </CardHeader>
        <CardBody>
          <NotificationsPreview />
        </CardBody>
      </Card>
    </>
  );
}

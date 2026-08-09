/**
 * InvestWizard — /mf/invest/[isin] client wizard.
 *
 * Reproduces docs/ui-system/html/TransactionExperienceV1.html (desktop) and
 * the mobile twin: sticky 6-step stepper, shared fund summary strip, sticky
 * order-summary rail (>=1100px) / bottom sheet (mobile), sticky footer.
 *
 * REAL BSE UAT sequence wired behind the design's steps:
 *   step1 details -> step2 GET ucc -> step3 SIP config (preview, BSE mandate
 *   gate) -> step4 payment method choice -> step5 POST /order -> step6
 *   approve/start -> approve/verify -> pg-link -> webhook-events polling.
 *
 * COMPLIANCE deltas from the design (binding, see task spec):
 *   - no "SEBI-registered investment adviser" / adviser-chat copy — AMFI
 *     distributor + ARN, email help@dhanradar.com.
 *   - no numeric DhanRadar score — riskometer TEXT badge only (parts.tsx).
 *   - no advisory verbs; consent checkbox starts UNCHECKED.
 *
 * Admin-gated client-side (UX only — the real boundary is RequireAdmin() on
 * every backend endpoint, same pattern as app/admin/layout.tsx).
 */
'use client';

import * as React from 'react';
import { notFound } from 'next/navigation';
import { useMe } from '@/features/auth/api';
import { api } from '@/lib/apiClient';
import { Button } from '@/components/ui/Button';
import { Card, CardBody } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  ChipRow,
  FundSummaryStrip,
  OrderSummaryPanel,
  StickyFooter,
  Stepper,
  DEMO_UCC,
  extractErrorText,
  matchesStage,
  computeLumpsumFuture,
  computeSipFuture,
  computeStepUpSipFuture,
  formatINR,
  yearlyCorpusSeries,
  type BseWebhookEvent,
  type FundHeadExt,
  type UccStatusObject,
} from './parts';
import { Step1, Step2, Step3, Step4, Step5, Step6 } from './steps';

// ---------------------------------------------------------------------------
// Wire types (all under /admin/bse-uat — see task spec for the contract).
// Shared helpers/constants (DEMO_UCC, extractErrorText, matchesStage) live in
// parts.tsx since steps.tsx (the render side) needs them too.
// ---------------------------------------------------------------------------
interface BseSessionResp { active: boolean; expires_in: number }
interface BseSchemeResp { found: boolean; scheme: Record<string, unknown> | null; cached: boolean }
interface BseUccResp { http_status: number; body: { data?: { ucc_status?: string; ucc_status_object?: UccStatusObject } } }
interface BseOrderResp { http_status: number; body: unknown; order_id: string | null; mem_ord_ref_id?: string }
interface BseApproveStartResp { ok: boolean; otp_sent: boolean; lids?: unknown }
interface BseApproveVerifyResp { approved: boolean; http_status: number; body: unknown }
interface BsePgLinkResp { pg_link: string | null }

const POLL_INTERVAL_MS = 5000;
const POLL_MAX_TICKS = 36; // 36 * 5s = 3 min

// ---------------------------------------------------------------------------

export default function InvestWizard({ isin, initialFundHead }: { isin: string; initialFundHead: FundHeadExt }) {
  const { data: user, isLoading } = useMe();

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 px-4 py-8 sm:px-6">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (!user?.is_admin) {
    notFound();
    return null;
  }

  return <InvestWizardInner isin={isin} fund={initialFundHead} contactEmail={user.email} />;
}

function InvestWizardInner({
  isin,
  fund,
  contactEmail,
}: {
  isin: string;
  fund: FundHeadExt;
  contactEmail: string;
}) {
  // --- BSE UAT session -------------------------------------------------
  const [sessionActive, setSessionActive] = React.useState<boolean | null>(null);
  const [bsePassword, setBsePassword] = React.useState('');
  const [sessionBusy, setSessionBusy] = React.useState(false);
  const [sessionErr, setSessionErr] = React.useState<string | null>(null);

  const refreshSession = React.useCallback(async () => {
    try {
      const s = await api.get<BseSessionResp>('/admin/bse-uat/session');
      setSessionActive(s.active);
    } catch {
      setSessionActive(false);
    }
  }, []);
  React.useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  async function loginBse() {
    setSessionBusy(true);
    setSessionErr(null);
    try {
      await api.post('/admin/bse-uat/session', { password: bsePassword });
      setBsePassword('');
      setSessionActive(true);
    } catch (e) {
      setSessionErr(e instanceof Error ? e.message : 'Login failed');
      setSessionActive(false);
    } finally {
      setSessionBusy(false);
    }
  }

  // --- scheme lookup (fires once, on mount, when session active) -------
  const [schemeCode, setSchemeCode] = React.useState<string | null>(null);
  const [schemeMinAmount, setSchemeMinAmount] = React.useState<number | null>(null);
  const [schemeLoading, setSchemeLoading] = React.useState(false);
  const [schemeError, setSchemeError] = React.useState<string | null>(null);
  const schemeFetched = React.useRef(false);

  React.useEffect(() => {
    if (!sessionActive || schemeFetched.current) return;
    schemeFetched.current = true;
    setSchemeLoading(true);
    api
      .get<BseSchemeResp>(`/admin/bse-uat/scheme?isin=${encodeURIComponent(isin)}`)
      .then((res) => {
        const scheme = res.scheme as
          | { scheme_bse_code?: string; lumpsum?: Array<{ scheme_transaction_single_details?: { scheme_transaction_amt?: number | string } }> }
          | null;
        if (scheme?.scheme_bse_code) setSchemeCode(scheme.scheme_bse_code);
        const rawMin = scheme?.lumpsum?.[0]?.scheme_transaction_single_details?.scheme_transaction_amt;
        const parsedMin = rawMin != null ? Number(rawMin) : NaN;
        if (!Number.isNaN(parsedMin) && parsedMin > 0) setSchemeMinAmount(parsedMin);
      })
      .catch((e) => setSchemeError(e instanceof Error ? e.message : 'Scheme lookup failed'))
      .finally(() => setSchemeLoading(false));
  }, [sessionActive, isin]);

  // --- step / navigation -------------------------------------------------
  const [step, setStep] = React.useState(1);
  const [sheetOpen, setSheetOpen] = React.useState(false);

  // --- step 1: details -----------------------------------------------
  const [investType, setInvestType] = React.useState<'sip' | 'lumpsum'>('sip');
  const [amount, setAmount] = React.useState(10000);
  const isLumpsum = investType === 'lumpsum';
  const skipStep3 = isLumpsum;

  const effectiveMin =
    schemeMinAmount ?? (isLumpsum ? fund.min_lumpsum_amount : fund.min_sip_amount) ?? null;
  const amountValid = effectiveMin == null || amount >= effectiveMin;

  // --- step 3: SIP setup -----------------------------------------------
  const [frequency, setFrequency] = React.useState<'monthly' | 'quarterly' | 'weekly'>('monthly');
  const [debitDate, setDebitDate] = React.useState(10);
  const [durationYears, setDurationYears] = React.useState(10);
  const [stepUpPct, setStepUpPct] = React.useState(10);

  // --- step 2: verification -----------------------------------------------
  const [uccLoading, setUccLoading] = React.useState(false);
  const [uccError, setUccError] = React.useState<string | null>(null);
  const [uccStatusObject, setUccStatusObject] = React.useState<UccStatusObject | null>(null);
  const [uccStatus, setUccStatus] = React.useState<string | null>(null);

  async function loadUcc() {
    setUccLoading(true);
    setUccError(null);
    try {
      const res = await api.get<BseUccResp>(`/admin/bse-uat/ucc/${DEMO_UCC}`);
      setUccStatus(res.body?.data?.ucc_status ?? null);
      setUccStatusObject(res.body?.data?.ucc_status_object ?? null);
    } catch (e) {
      setUccError(e instanceof Error ? e.message : 'Failed to load investor profile');
    } finally {
      setUccLoading(false);
    }
  }

  // --- step 4: payment -----------------------------------------------
  const [paymentMethod, setPaymentMethod] = React.useState<'upi'>('upi');

  // --- step 5: review + confirm -----------------------------------------------
  const [consent, setConsent] = React.useState(false);
  const [orderSubmitting, setOrderSubmitting] = React.useState(false);
  const [orderError, setOrderError] = React.useState<string | null>(null);
  const [orderId, setOrderId] = React.useState<string | null>(null);

  const canConfirm = !isLumpsum ? false : sessionActive === true && consent && amountValid && !!schemeCode;

  async function confirmOrder() {
    if (!schemeCode) {
      setOrderError('No BSE scheme code resolved yet — reopen step 1 to retry the scheme lookup.');
      return;
    }
    setOrderSubmitting(true);
    setOrderError(null);
    try {
      const res = await api.post<BseOrderResp>('/admin/bse-uat/order', {
        scheme_code: schemeCode,
        amount,
        contact_email: contactEmail,
      });
      if (res.order_id) {
        setOrderId(res.order_id);
        setStep(6);
      } else {
        setOrderError(extractErrorText(res.body));
      }
    } catch (e) {
      setOrderError(e instanceof Error ? e.message : 'Order submission failed');
    } finally {
      setOrderSubmitting(false);
    }
  }

  // --- step 6: approve / pay / track -----------------------------------------------
  const [otp, setOtp] = React.useState('');
  const [otpSending, setOtpSending] = React.useState(false);
  const [otpSent, setOtpSent] = React.useState(false);
  const [otpError, setOtpError] = React.useState<string | null>(null);
  const [approving, setApproving] = React.useState(false);
  const [approved, setApproved] = React.useState(false);
  const [approveError, setApproveError] = React.useState<string | null>(null);
  const [pgLoading, setPgLoading] = React.useState(false);
  const [pgError, setPgError] = React.useState<string | null>(null);
  const [events, setEvents] = React.useState<BseWebhookEvent[]>([]);

  async function startApproval() {
    if (!orderId) return;
    setOtpSending(true);
    setOtpError(null);
    try {
      const res = await api.post<BseApproveStartResp>(`/admin/bse-uat/order/${orderId}/approve/start`);
      setOtpSent(!!res.otp_sent);
      if (!res.otp_sent) setOtpError('BSE did not confirm an OTP was sent — check the order status below.');
    } catch (e) {
      setOtpError(e instanceof Error ? e.message : 'Failed to send OTP');
    } finally {
      setOtpSending(false);
    }
  }

  async function verifyApproval() {
    if (!orderId) return;
    setApproving(true);
    setApproveError(null);
    try {
      const res = await api.post<BseApproveVerifyResp>(`/admin/bse-uat/order/${orderId}/approve/verify`, { otp });
      if (res.approved) setApproved(true);
      else setApproveError(extractErrorText(res.body));
    } catch (e) {
      setApproveError(e instanceof Error ? e.message : 'Approval failed');
    } finally {
      setApproving(false);
    }
  }

  async function openPgLink() {
    if (!orderId) return;
    setPgLoading(true);
    setPgError(null);
    try {
      const res = await api.get<BsePgLinkResp>(`/admin/bse-uat/order/${orderId}/pg-link`);
      if (res.pg_link) {
        window.open(res.pg_link, '_blank', 'noopener,noreferrer');
      } else {
        setPgError('Payment link is not ready yet — try again in a few seconds.');
      }
    } catch (e) {
      setPgError(e instanceof Error ? e.message : 'Failed to fetch the payment link');
    } finally {
      setPgLoading(false);
    }
  }

  // webhook-events polling — every 5s, stop after 3 min or once exch_init lands.
  React.useEffect(() => {
    if (!orderId) return;
    let cancelled = false;
    let ticks = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function tick() {
      try {
        const rows = await api.get<BseWebhookEvent[]>(
          `/admin/bse-uat/webhook-events?order_id=${encodeURIComponent(orderId as string)}&limit=50`,
        );
        if (cancelled) return;
        setEvents(rows);
        ticks++;
        if (rows.some((r) => matchesStage(r, 'exch_init')) || ticks >= POLL_MAX_TICKS) return;
      } catch {
        ticks++;
        if (ticks >= POLL_MAX_TICKS) return;
      }
      if (!cancelled) timer = setTimeout(tick, POLL_INTERVAL_MS);
    }
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [orderId]);

  // --- derived: projections (illustrative, client-side only) -----------------------------------------------
  const projection = React.useMemo(() => {
    if (isLumpsum) {
      return {
        conservative: computeLumpsumFuture(amount, durationYears, 9),
        expected: computeLumpsumFuture(amount, durationYears, 13),
        optimistic: computeLumpsumFuture(amount, durationYears, 16),
        invested: amount,
      };
    }
    return {
      conservative: computeSipFuture(amount, durationYears, 9),
      expected: computeSipFuture(amount, durationYears, 13),
      optimistic: computeSipFuture(amount, durationYears, 16),
      invested: amount * 12 * durationYears,
    };
  }, [amount, durationYears, isLumpsum]);

  const growthSeries = React.useMemo(
    () => yearlyCorpusSeries(isLumpsum, amount, Math.min(durationYears, 10), 13),
    [isLumpsum, amount, durationYears],
  );

  const stepUpOutcome = React.useMemo(
    () => computeStepUpSipFuture(amount, durationYears, 13, stepUpPct),
    [amount, durationYears, stepUpPct],
  );
  const flatOutcome = React.useMemo(() => computeSipFuture(amount, durationYears, 13), [amount, durationYears]);

  // --- nav helpers -----------------------------------------------
  const stepOrder = skipStep3 ? [1, 2, 4, 5, 6] : [1, 2, 3, 4, 5, 6];
  function goNext() {
    const idx = stepOrder.indexOf(step);
    const next = idx >= 0 && idx < stepOrder.length - 1 ? stepOrder[idx + 1] : step;
    setStep(next);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  function goBack() {
    const idx = stepOrder.indexOf(step);
    const prev = idx > 0 ? stepOrder[idx - 1] : step;
    setStep(prev);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  function jumpTo(n: number) {
    setStep(n);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  const footerMeta: Record<number, { label: string; value: string; nextLabel: string; nextDisabled?: boolean }> = {
    1: { label: 'Step 1 of 6 · Investment details', value: investType === 'sip' ? `${formatINR(amount)} / month` : formatINR(amount), nextLabel: 'Continue to verification →', nextDisabled: !amountValid },
    2: { label: 'Step 2 of 6 · Verification', value: uccStatus ? `UCC ${uccStatus}` : 'Not loaded yet', nextLabel: skipStep3 ? 'Continue to payment →' : 'Continue to SIP setup →' },
    3: { label: 'Step 3 of 6 · SIP configuration', value: `${formatINR(amount)} · ${frequency} · ${durationYears}y`, nextLabel: 'Continue to payment →' },
    4: { label: 'Step 4 of 6 · Payment', value: `${paymentMethod.toUpperCase()} · ${formatINR(amount)}`, nextLabel: 'Continue to review →' },
    5: {
      label: 'Step 5 of 6 · Review & confirm',
      value: formatINR(amount),
      nextLabel: isLumpsum ? (orderSubmitting ? 'Placing order…' : 'Confirm & place order') : 'SIP setup — awaiting BSE enablement',
      nextDisabled: isLumpsum ? !canConfirm || orderSubmitting : true,
    },
    6: { label: 'Step 6 of 6 · Done', value: orderId ? `Order ${orderId}` : 'Awaiting order', nextLabel: 'Done' },
  };
  const meta = footerMeta[step];

  function handleFooterNext() {
    if (step === 5) {
      if (isLumpsum) void confirmOrder();
      return;
    }
    if (step === 6) return;
    goNext();
  }

  return (
    <div className="mx-auto max-w-6xl px-4 pb-28 pt-6 sm:px-6">
      {/* BSE session bar */}
      <Card className="mb-4">
        <CardBody className="flex flex-wrap items-center gap-3">
          <ChipRow kinds={['live', 'uat']} />
          <span className="text-small font-medium text-ink">BSE UAT session</span>
          <span className={sessionActive ? 'text-caption text-emerald' : 'text-caption text-ink-muted'}>
            {sessionActive === null ? 'Checking…' : sessionActive ? 'Active' : 'Not active'}
          </span>
          {!sessionActive && (
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <Input
                type="password"
                placeholder="BSE member password"
                value={bsePassword}
                onChange={(e) => setBsePassword(e.target.value)}
                className="w-56"
              />
              <Button size="sm" onClick={loginBse} disabled={sessionBusy || !bsePassword}>
                {sessionBusy ? 'Logging in…' : 'Login to BSE UAT'}
              </Button>
            </div>
          )}
        </CardBody>
        {sessionErr && <p className="px-6 pb-3 text-small text-red">{sessionErr}</p>}
      </Card>

      <Stepper current={step} skipStep3={skipStep3} onJump={jumpTo} />

      <div className="mt-4 grid grid-cols-1 gap-5 min-[1100px]:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-4">
          <FundSummaryStrip fund={fund} />

          {step === 1 && (
            <Step1
              fund={fund}
              investType={investType}
              setInvestType={setInvestType}
              amount={amount}
              setAmount={setAmount}
              effectiveMin={effectiveMin}
              amountValid={amountValid}
              schemeLoading={schemeLoading}
              schemeError={schemeError}
              sessionActive={sessionActive}
              projection={projection}
              growthSeries={growthSeries}
              durationYears={durationYears}
            />
          )}

          {step === 2 && (
            <Step2
              uccLoading={uccLoading}
              uccError={uccError}
              uccStatus={uccStatus}
              uccStatusObject={uccStatusObject}
              onLoad={loadUcc}
              sessionActive={sessionActive}
            />
          )}

          {step === 3 && (
            <Step3
              amount={amount}
              setAmount={setAmount}
              frequency={frequency}
              setFrequency={setFrequency}
              debitDate={debitDate}
              setDebitDate={setDebitDate}
              durationYears={durationYears}
              setDurationYears={setDurationYears}
              stepUpPct={stepUpPct}
              setStepUpPct={setStepUpPct}
              stepUpOutcome={stepUpOutcome}
              flatOutcome={flatOutcome}
            />
          )}

          {step === 4 && (
            <Step4
              paymentMethod={paymentMethod}
              setPaymentMethod={setPaymentMethod}
              sessionActive={sessionActive}
            />
          )}

          {step === 5 && (
            <Step5
              fund={fund}
              isin={isin}
              investType={investType}
              amount={amount}
              frequency={frequency}
              debitDate={debitDate}
              schemeCode={schemeCode}
              consent={consent}
              setConsent={setConsent}
              orderError={orderError}
              isLumpsum={isLumpsum}
              sessionActive={sessionActive}
              amountValid={amountValid}
            />
          )}

          {step === 6 && (
            <Step6
              orderId={orderId}
              fund={fund}
              amount={amount}
              otp={otp}
              setOtp={setOtp}
              otpSending={otpSending}
              otpSent={otpSent}
              otpError={otpError}
              onStartApproval={startApproval}
              approving={approving}
              approved={approved}
              approveError={approveError}
              onVerifyApproval={verifyApproval}
              pgLoading={pgLoading}
              pgError={pgError}
              onOpenPgLink={openPgLink}
              events={events}
            />
          )}
        </div>

        {/* desktop rail — panel + help card share ONE sticky wrapper, else the
            stuck panel slides over the in-flow card below it on scroll */}
        <aside className="hidden min-[1100px]:block">
          <div className="sticky top-28 space-y-4">
          <div className="overflow-hidden rounded-lg border border-line shadow-md">
            <OrderSummaryPanel
              fund={fund}
              investType={investType}
              amount={amount}
              frequency={frequency}
              debitDate={debitDate}
              orderId={orderId}
            />
          </div>
          <Card>
            <CardBody>
              <div className="text-small font-semibold text-ink">Need a hand?</div>
              <p className="mt-1 text-caption text-ink-secondary">
                Email help@dhanradar.com — we are an AMFI-registered Mutual Fund Distributor, not an
                adviser, so we can help with process questions, not investment advice.
              </p>
            </CardBody>
          </Card>
          </div>
        </aside>
      </div>

      {/* mobile bottom sheet */}
      {sheetOpen && (
        <div className="fixed inset-0 z-40 min-[1100px]:hidden">
          <button
            aria-label="Close order summary"
            className="absolute inset-0 bg-navy/50"
            onClick={() => setSheetOpen(false)}
          />
          <div className="absolute inset-x-0 bottom-0 max-h-[82%] overflow-y-auto rounded-t-2xl bg-surface shadow-lg">
            <div className="mx-auto mt-2 h-1 w-9 rounded-full bg-line" />
            <OrderSummaryPanel
              fund={fund}
              investType={investType}
              amount={amount}
              frequency={frequency}
              debitDate={debitDate}
              orderId={orderId}
            />
          </div>
        </div>
      )}

      <StickyFooter
        label={meta.label}
        value={meta.value}
        onBack={goBack}
        backHidden={step === 1}
        onNext={handleFooterNext}
        nextLabel={meta.nextLabel}
        nextDisabled={meta.nextDisabled}
        nextBusy={step === 5 && orderSubmitting}
        onOpenSheet={() => setSheetOpen(true)}
      />
    </div>
  );
}


/**
 * E7 — Loan / EMI engine.
 *
 * Equated Monthly Instalment + a full month-by-month amortization, snapshotted
 * per year for the chart/table. Pure, deterministic, clamped — never NaN/Infinity.
 *
 *   EMI = P · r · (1+r)^n / ((1+r)^n − 1)   (r = annual/12/100, n = months; r=0 → P/n)
 */
import { MAX_AMOUNT, MAX_YEARS } from './accumulation';

export const MAX_LOAN_RATE_PCT = 40;

export interface LoanInput {
  /** Loan amount (principal) in ₹. */
  principal: number;
  /** Annual interest rate %, 0–40. */
  annualRatePct: number;
  /** Tenure in years, 0–50. */
  years: number;
}

export interface LoanYearPoint {
  year: number;
  principalPaid: number; // cumulative principal repaid by end of year
  interestPaid: number; // cumulative interest paid by end of year
  balance: number; // outstanding balance at end of year
}

export interface LoanResult {
  emi: number;
  totalInterest: number;
  totalPayment: number;
  series: LoanYearPoint[];
}

function clampFinite(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

/** Compute EMI + a yearly amortization schedule. */
export function computeLoan(input: LoanInput): LoanResult {
  const principal = clampFinite(input.principal, 0, MAX_AMOUNT);
  const rate = clampFinite(input.annualRatePct, 0, MAX_LOAN_RATE_PCT);
  const years = clampFinite(input.years, 0, MAX_YEARS);

  const r = rate / 100 / 12;
  const n = Math.round(years * 12);

  let emi: number;
  if (n === 0) emi = 0;
  else if (r === 0) emi = principal / n;
  else {
    const g = Math.pow(1 + r, n);
    emi = (principal * r * g) / (g - 1);
  }
  if (!Number.isFinite(emi)) emi = 0;

  // Month-by-month amortization, snapshotted at each year end (and the final month).
  let balance = principal;
  let cumPrincipal = 0;
  let cumInterest = 0;
  const series: LoanYearPoint[] = [{ year: 0, principalPaid: 0, interestPaid: 0, balance: principal }];
  for (let m = 1; m <= n; m += 1) {
    const interest = balance * r;
    let principalComponent = emi - interest;
    if (principalComponent > balance) principalComponent = balance; // final instalment
    balance = Math.max(balance - principalComponent, 0);
    cumPrincipal += principalComponent;
    cumInterest += interest;
    if (m % 12 === 0 || m === n) {
      series.push({
        year: Math.ceil(m / 12),
        principalPaid: cumPrincipal,
        interestPaid: cumInterest,
        balance,
      });
    }
  }

  const totalInterest = Number.isFinite(cumInterest) ? cumInterest : 0;
  const totalPayment = Number.isFinite(cumPrincipal + cumInterest) ? cumPrincipal + cumInterest : 0;

  return { emi, totalInterest, totalPayment, series };
}

# Data Reconciliation Engine

## Purpose
Guarantee that what we store + score matches the authoritative exchange/AMFI record, and that corporate-action adjustments are correct.

## Reconciliation passes
1. **Intraday→EOD:** at close, overwrite intraday snapshots with authoritative bhavcopy OHLC; log deltas.
2. **Vendor↔Exchange:** compare vendor EOD vs exchange bhavcopy per symbol; variance > tolerance → flag + quarantine + alert.
3. **Cross-venue:** NSE vs BSE price for dual-listed within band; pick canonical.
4. **CA continuity:** after each adjustment, assert market-cap continuity + holding-value continuity (pre/post within tolerance); mismatch → block + DLQ + alert.
5. **NAV:** AMFI NAV vs prior + scheme master; impossible jumps flagged.
6. **Holdings:** user holdings post-CA reconcile (qty×price invariants).

## Mechanics
- Nightly job (Celery) emits a **reconciliation report** → Data Source Monitor.
- Tolerances configurable per asset class; CA continuity tolerance near-zero.
- Discrepancies create incidents with replay tooling; authoritative source wins.

## Tests (CI, golden fixtures)
- Split 1:2, bonus 1:1, rights, name-change → expected adjusted series + holdings.
- Variance injection → expect quarantine + alert.

## Outputs
- `reconciliation_runs(id, scope, variances jsonb, status, ts)`; alerts; audit of every correction.

# Model Versioning Framework

## Versioning
- `model_version` (e.g., v2.4) encodes: factor weights, sub-factor weights (per sector), normalization params, signal bands, fair-value blend.
- Config is **declarative + version-controlled**; a version is immutable once published.
- Every `scores` row carries its model_version → fully reproducible + auditable.

## Lifecycle
```
DRAFT → BACKTEST (gates) → CANARY (% of read traffic via flag) → ANALYSIS → PROMOTE | ROLLBACK → RETIRED
```
- **Canary:** serve new version to N% of read traffic; compare live deltas + complaints + eval.
- **Promote:** repoint "active" pointer; **no data migration** (both versions' scores coexist).
- **Rollback:** repoint to prior version instantly.
- **A/B:** weights/normalization variants compared on backtest + live IC.

## Governance
- Change to weights/bands/copy → **compliance review** (signal framing) + research sign-off + backtest gates.
- AI-Ops dashboard: active version, canary %, backtest spread/IC, drift, calibration curve, rollback control.
- Audit: who changed what, when, approvals.

## Reproducibility
- Given (inputs snapshot + model_version) the Score is bit-reproducible — required for regulatory defensibility (compliance audit trail).

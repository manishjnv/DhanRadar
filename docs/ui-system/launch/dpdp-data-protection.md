# DPDP Act Data Protection Program (F3)

India **Digital Personal Data Protection Act 2023** compliance.

## Controls
- **Consent:** explicit, purpose-bound, recorded (timestamp, version) at signup + for portfolio/AI use. Granular toggles (marketing off by default; "use my portfolio for insights" opt-in).
- **Data map:** maintain inventory of PII (email, phone, holdings) → store, purpose, retention, processor.
- **Rights:** self-serve data **export** + **erasure** (soft-delete + scheduled purge; audit-preserved per legal retention).
- **Minimization:** collect only what's needed; never store broker credentials (AA framework).
- **Breach process:** detection → contain → notify Data Protection Board + affected users within statutory window.
- **DPO / grievance officer:** named contact published; grievance SLA.
- **Processors:** DPAs with all sub-processors (cloud, email, SMS, LLM, payments).
- **Cross-border:** confirm LLM/data processing locations meet transfer rules.

## Launch gate (P0)
- [ ] Consent records implemented + versioned
- [ ] Export + erasure flows live
- [ ] Data map + DPAs complete
- [ ] Grievance officer published

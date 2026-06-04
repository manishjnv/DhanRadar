# Recommendation Audit Trail & Evidence Retention

## What is logged (immutable, hash-chained)
For **every recommendation/AI output shown to a user**:
- timestamp, user_id (or anon id), surface, instrument(s)
- score + signal + factors + model_version + confidence
- inputs snapshot ref (data as_of, sources)
- disclosures rendered (ids + version)
- AI: prompt_version, retrieval source ids, safety result
- user acknowledgements (disclaimer seen/accepted), risk_profile_version
- request_id (trace correlation)

## Schema
```sql
CREATE TABLE recommendation_audit (
  id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ DEFAULT now(),
  user_id UUID, surface TEXT, instrument_id UUID,
  score INT, signal TEXT, model_version TEXT, confidence INT,
  inputs_ref TEXT, disclosures JSONB, ai JSONB,
  risk_profile_version TEXT, request_id UUID,
  prev_hash TEXT, hash TEXT  -- tamper-evident chain
);
```
- Append-only; `hash = H(prev_hash || row)`; periodic anchor of latest hash to WORM storage.

## Retention
- **Recommendation/research evidence:** retain **≥ 5 years** (align to SEBI RA record-keeping; confirm exact period with counsel) in WORM storage.
- **Audit log (security/admin):** 400 days hot → WORM for regulatory window.
- **Risk profiles, consents:** life of account + statutory tail; erasable per DPDP with audit-preserved tombstone.
- **AI interactions:** retained for eval/defensibility; user-exportable; consent-gated training use.

## Access
- Audit access is itself audited; export tooling for regulator requests; legal-hold capability (suspend purge).

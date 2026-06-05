# Account Aggregator Consent Spec (F4)

Broker/portfolio data via the **RBI Account Aggregator** framework — consent-based, revocable, no credential storage.

## Flow
```
User → "Connect broker" → redirect to AA (consent artifact: purpose, data types, duration, frequency)
  → user approves in AA app → AA issues consent_id + token
  → DhanRadar fetches FI data via AA (never the broker password)
  → store consent_id + status in broker_links; schedule periodic fetch per consent frequency
Revoke: user revokes in-app or in AA → we stop fetching, mark consent revoked, optionally purge synced holdings
```

## Rules
- **Never** store or request broker credentials. Only AA tokens/consent ids.
- Honor consent **duration + frequency**; stop on expiry/revocation.
- Encrypt consent tokens at rest (KMS); audit every fetch + revocation.
- Fallback: **manual holding entry** when AA unavailable.

## Launch gate (P0)
- [ ] AA TSP integration tested (sandbox → prod)
- [ ] Revocation + purge verified
- [ ] Audit of every fetch

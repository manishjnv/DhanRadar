# Secrets & Key Management Runbook (F7)

## JWT (RS256)
- **Generate:** `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out jwt_rs256.pem && openssl rsa -in jwt_rs256.pem -pubout -out jwt_rs256.pub`
- Store private key in **Vault/KMS** (never in repo/image). Public key served via **JWKS** (kid rotation).
- **Rotation:** issue new kid, dual-publish (old+new) in JWKS, sign with new, retire old after max token TTL. Refresh-token sessions unaffected (opaque).

## Secrets
- All secrets in Vault/cloud Secrets Manager; apps fetch via CSI/sidecar. **No env files in images.**
- Dynamic DB credentials (short TTL) where supported; static rotated on schedule + on incident.
- CI: OIDC federation → short-lived cloud tokens; **no static cloud keys in GitHub**. gitleaks scan blocks secrets in commits.

## Rotation cadence
- JWT signing keys: 90 days. DB creds: 30 days (dynamic) / on incident. Webhook secrets: on incident. API keys (Premium): user-revocable.

## Launch gate (P0)
- [ ] Keys generated + in Vault; JWKS live
- [ ] Rotation procedure tested
- [ ] No secrets in repo/images (gitleaks clean)

# DhanRadar — RCA Log (Root Cause Analysis)

Every bug fix gets an entry here. This is a standing rule: a fix is not "done" until its RCA is written. New entries go at the top (newest first). Keep each entry short and concrete — the goal is that a future session never re-hits the same trap.

## Entry template (copy this)

```
### YYYY-MM-DD — <short title>
- **Symptom:** what was observed (the failure as seen, not the guess).
- **Root cause:** the actual underlying reason, proven not assumed.
- **Fix:** what changed, with file:line references.
- **Prevention:** the guard added so this class of bug cannot recur (test, check, lint, doc rule, config).
- **Phase/area:** which phase or module.
```

## Log

### 2026-05-19 — Auth slice: rate limiter built but unwired; refresh rotation non-atomic

- **Symptom:** found in pre-merge security review of the Phase-2 Auth slice (not a field incident). (a) `RateLimit` dependency existed in `ratelimit.py` but was attached to no route → `/auth/login` had no brute-force throttle. (b) `rotate_refresh_token` did `redis.get` then `redis.delete` → two concurrent uses of one refresh token could both succeed, defeating reuse detection.
- **Root cause:** (a) limiter authored as a reusable dependency but the wiring step was never done — "exists" was mistaken for "applied". (b) read-then-delete is not atomic; the reuse-detection invariant requires single-consumer semantics.
- **Fix:** (a) `Depends(_rl_login/_rl_signup/_rl_refresh/_rl_totp)` wired onto the auth endpoints, keyed by `CF-Connecting-IP` (XFF is client-spoofable behind the tunnel) — `auth/router.py`, `ratelimit.py:_get_client_ip`. (b) atomic `redis.getdel(key)` + owner-match assert — `auth/service.py rotate_refresh_token`. Plus adversarial-gate fixes: logout access-jti revocation, webhook event-id idempotency, exact-plan-id map, password `max_length`.
- **Prevention:** a security control is not "done" until it is wired to a route AND exercised by a test (e2e auth test owed before deploy — Phase 7 §5). Rule: any Redis check-then-act on an auth-critical key must use an atomic primitive (`GETDEL`/`SET NX`/Lua), never GET-then-DELETE. Both recorded in `docs/features/auth.md` "Known limitations".
- **Phase/area:** Phase 2 / Auth & Tiering.

### 2026-05-19 — Malformed table row in architecture doc (data being dropped)

- **Symptom:** markdownlint `MD056/table-column-count` at `docs/DhanRadar_Architecture_Final.md:234` — header had 3 columns, the row produced 6; "extra data will be missing" (the cell was being mis-rendered/truncated).
- **Root cause:** the cell contained literal `|` pipes inside an inline code span (`{ status: queued|processing|done|failed }`); markdown's table parser treats `|` as a column separator even inside backticks.
- **Fix:** escaped the pipes as `\|` in that cell — `docs/DhanRadar_Architecture_Final.md:234`.
- **Prevention:** repo `.markdownlint.json` keeps `MD056` enabled (only opinionated/cosmetic rules disabled), so genuinely broken tables keep failing the lint; pipes inside table cells must always be `\|`.
- **Phase/area:** Docs / markdown-lint pass.

### 2026-05-18 — Cloudflare tunnel CNAME mis-targeted to etip-ssh

- **Symptom:** after `cloudflared tunnel route dns dhanradar dhanradar.com`, the `dhanradar.com` DNS record pointed at tunnel `6e263591` (etip-ssh) instead of the new `dhanradar` tunnel `df2c5ae4`.
- **Root cause:** `cloudflared tunnel route dns <NAME> …` resolves the tunnel using the default `/etc/cloudflared/config.yml` (which is etip-ssh's), ignoring the name argument.
- **Fix:** corrected the DNS record to `df2c5ae4-….cfargotunnel.com` (Cloudflare DNS UI); verified HTTP/2 200 end-to-end.
- **Prevention:** plan + `infra-notes.md` now mandate explicit tunnel **UUID + `--overwrite-dns`** for `route dns`; never rely on the tunnel name when a default config exists.
- **Phase/area:** Phase 1 / Cloudflare tunnel setup.

### 2026-05-18 — pkill self-terminated the SSH session

- **Symptom:** a verification SSH command exited 255 with truncated output during cleanup.
- **Root cause:** `pkill -f "cloudflared-dhanradar/config.yml"` matched the SSH shell's own command line (the pattern appeared in the script text), killing the session.
- **Fix:** re-verified state with a self-safe method.
- **Prevention:** standing rule in plan/infra-notes — never `pkill -f <pattern>` where the pattern can appear in your own command line; enumerate with `pgrep -x cloudflared` and check `/proc/<pid>/cmdline` per pid.
- **Phase/area:** Phase 1 / process cleanup over SSH.

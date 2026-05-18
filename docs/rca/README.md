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

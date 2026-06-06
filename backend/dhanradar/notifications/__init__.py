"""DhanRadar — Notification module (Phase 6, architecture Global §5).

Owns ALL outbound delivery (Telegram + Resend email at launch; WhatsApp is Y2) and
the Pillow share-card PNG service. It is delivery-only: it generates no content —
domains (Alert/Mood/Nudge/Gamification/MF) publish structured jobs and this module
renders a fixed template, enforces quiet-hours + per-channel rate caps, delivers,
and logs.

Compliance posture (delivery is a label surface):
  * Templates render the verb-label + the SEBI disclosure + NOT_ADVICE — never a
    numeric score / factor weight / fair value (non-neg #2) and never an advisory
    verb (buy/sell/hold/switch/avoid, non-neg #1).
  * Email goes through Resend (NOT SendGrid, non-neg #8) and MUST send a real
    User-Agent — api.resend.com is behind Cloudflare and 403s the default
    python-urllib UA (error 1010); httpx sends its own UA, set explicitly here.
"""

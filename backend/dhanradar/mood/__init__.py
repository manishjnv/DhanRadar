"""DhanRadar — Mood Compass module (architecture Mood Compass Module).

Twice-daily market regime score (0–100) over 11 weighted macro/market inputs →
5 buckets + a best-effort plain-English commentary. Owns `market_mood` + `mood:*`
Redis. Delivery is NOT here — it emits `mood.snapshot.published` and posts the daily
public card via the Notification interface.

Compliance posture: the regime is EXPLICITLY DISTINCT from the per-security
DhanRadar Score (never a ranking input). The numeric 0–100 is server-side; the
public surface is the `regime` bucket + `confidence_band` + commentary + the
contributing/contradicting evidence — no number (non-neg #2), no advice (non-neg #1),
disclosure injected (non-neg #9).
"""

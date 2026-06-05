# Onboarding & Activation Spec (F10)

## North-star: time-to-first-value < 60s
**Activation = added 1 watchlist item OR ran 1 AI explain OR synced a broker.**

## Flow (compressed)
```
SEO stock page (ungated score + 1 free AI explain)
  → "See full analysis" → Signup (email/phone/password OR social, no card)
  → OTP verify
  → Onboarding (single screen): pick 1-2 interests + optional "paste holdings" OR "skip"
  → Dashboard pre-filled (watchlist from interests/paste) + cold-start card
```
- Defer profile questions to post-activation. Marketing opt-in OFF by default.

## Cold-start (empty dashboard)
- One **"Get started in 60s"** card with 3 one-tap paths: Sync broker · Add 3 top-scored · Run a preset screen.
- Replace scattered empty states with this single guided card until the user has ≥1 holding/watchlist item.

## Metrics
- signup→activation rate (target ≥ 60% of signups), time-to-first-value, D1/D7/D30 retention.

## Launch gate (P1)
- [ ] Flow implemented with no-card trial
- [ ] Cold-start card live
- [ ] Activation event instrumented

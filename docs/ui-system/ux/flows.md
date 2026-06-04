# User Flows

### Flow A — Public → Activation (acquisition, primary)
```
SEO landing (Stock Detail preview)
  → sees Score + 1-line reason (ungated)
  → taps "Why 86?" → AI explain teaser (1 free)
  → hits "see full analysis" → Sign Up (no card)
  → OTP verify
  → Onboarding (goals, paste/sync holdings, pick interests)
  → Dashboard (pre-populated watchlist)
  ✦ Activation = added 1 watchlist item OR ran 1 AI explain
```

### Flow B — Free → Paid (conversion)
```
Authenticated user researching
  → hits gated feature (Fair Value / unlimited AI / screener save)
  → contextual paywall (shows the value they're reaching for)
  → Pricing / Plan select
  → Razorpay checkout (UPI/card/netbanking)
  → confirmation → feature unlocked inline
  ✦ Conversion at demonstrated-value moment, not arbitrary limit
```

### Flow C — Research a stock (core JTBD #1–2)
```
Search (⌘K) or Dashboard tile
  → Stock Detail
  → read Score + factor breakdown
  → tap "explain" on any metric → AI inline answer
  → check Fair Value (🟣 gate if Free)
  → Compare with peer (add 2nd, 3rd)
  → Decide → Add to Watchlist / Set Alert / (broker handoff)
```

### Flow D — Monitor portfolio (core JTBD #3)
```
Connect broker (AA framework) OR manual add
  → Portfolio Overview (value + Portfolio Score)
  → review Holdings (per-holding scores)
  → Analytics (🟣: risk, sector exposure, attribution)
  → receive monthly Health Report (🟣)
  → Alert fires on material change → re-evaluate holding
```

### Flow E — Set up an alert
```
Stock/Fund/Portfolio context
  → "Set alert" → choose type (price / score / risk / earnings)
  → set threshold → confirm
  → Alerts Center (manage)
  → trigger → push/email → deep link back to instrument
```

### Flow F — Learn while doing
```
Hit unknown term anywhere → "explain" tooltip → Glossary term
  → related Lesson → Topic → Learn Hub
  → progress tracked → streak → resume card on Dashboard
```

### Flow G — Admin: publish content
```
Admin login → Content CMS → new article/lesson
  → draft → preview → SEO meta → schedule/publish → live on Public
```

### Flow H — AI Ops: ship a score model version
```
AI Ops → Score Model Versioning
  → new version → backtest vs benchmark → eval gates
  → canary % rollout → monitor (drift, complaints) → full rollout / rollback
```

---
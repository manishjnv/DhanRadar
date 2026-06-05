# Growth Metrics & North Star

## North Star Metric
**Weekly Researching Investors (WRI):** users who run ≥1 meaningful research action (score view + explain / screener / compare / AI) in a week.
- Captures the core value (research that informs decisions), leads revenue, and is honest (not vanity).
- Supporting inputs: activation rate × engagement frequency × retention.

## Metric tree
```
North Star: WRI
├── New researching investors (acquisition × activation)
│     ├── traffic (SEO, referral) × signup rate
│     └── activation rate (first value <60s)
├── Retained researching investors (retention)
│     └── habit loops (watchlist→alert→re-evaluate)
└── Depth per investor (engagement)
      └── research depth, AI usage, portfolio sync
Revenue (lagging): paying users × ARPU = MRR  (conversion from WRI)
```

## KPI set (with targets, y2)
| Category | KPI | Target |
|---|---|---|
| Acquisition | signups/wk; CAC; channel mix | CAC < ₹600 |
| Activation | activation rate; TTFV | ≥60%; <60s |
| Engagement | WRI; actions/active; AI adoption | grow WoW |
| Retention | D30; DAU/MAU | D30 ≥35%; stickiness ≥25% |
| Referral | K-factor; referral signups | K ≥ 0.3 |
| Subscription | Free→Pro; trial→paid; churn | 4–6%; ≥35%; <4% |
| Revenue | MRR; ARPU; LTV:CAC | LTV:CAC >4 |
| Recommendation | rec CTR; rec conversion | grow |
| AI | AI adoption; helpful-rate | ≥85% helpful |
| Cost | AI ₹/user; gross margin | margin >80% |

## Experimentation
- Hypothesis → metric → A/B (PostHog flags) → significance → ship/kill. North Star + guardrails (don't grow signups while tanking activation).

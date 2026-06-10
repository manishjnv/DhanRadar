# DhanRadar Score Model (v2.4) — exact spec

## Pipeline
1. **Per-factor raw metrics** (per instrument):
   - valuation: composite of PE, PB, EV/EBITDA vs sector (lower = better)
   - growth: revenue CAGR(3y/5y), EPS growth, sales momentum
   - quality: ROE, operating margin, FCF margin, debt/equity (inverse)
   - momentum: 3m/6m price return, 50/200-DMA cross, earnings revisions
   - risk: beta, volatility(30d), max drawdown(1y), debt — higher score = lower risk
2. **Normalize** each factor within the instrument's sector+peer set: z-score → clamp [-3,3] → map to 0–100 (50 = sector median).
3. **Composite** (weights, sum=1.0):
   ```
   score = round( 0.22*valuation + 0.22*growth + 0.24*quality + 0.20*momentum + 0.12*risk )
   ```
4. **Signal band:** ≥85 strong_buy · ≥70 buy · ≥55 hold · ≥40 caution · <40 avoid.
5. **Fair value:** weighted DCF(0.5) + relative-PE(0.3) + EPV(0.2) → target; upside = (target-price)/price.
6. **Confidence (0–100):** `0.30*freshness + 0.25*coverage + 0.20*factor_agreement + 0.15*retrieval_relevance + 0.10*model_signal`. Bands: High ≥75 / Moderate 50–74 / Low <50.

## Rules
- Deterministic; reproducible from inputs + version weights. No LLM in the number.
- Funds use fund-specific factors (rolling returns, Sharpe, downside capture, expense, manager tenure) under the same 5-factor frame.
- Versioned (`model_version`); canary via flag; rollback by repointing active version.
- Recompute nightly 18:30 IST; write immutable `scores(as_of, model_version)`.

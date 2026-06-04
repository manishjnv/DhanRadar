# DhanRadar Recommendation Engine Spec

> **Superseded for production by `/recommendation-engine`** — the full quant spec (factor catalog, score/confidence/risk formulas, normalization, missing-data, sector/liquidity adjustments, news-sentiment, backtesting, benchmarks, model versioning, lifecycle). This file remains a quick summary.


Deterministic quant pipeline (nightly 18:30 IST, Celery `scoring`): factor compute (valuation/growth/quality/momentum/risk) → sector-normalize (z→0-100) → weighted composite (model_version) → signal band → fair value (DCF+relative+EPV) → write immutable scores(as_of, model_version) → diff → score-change events → AI pre-generates explanations. AI never generates the number. Versioned: canary % via feature flag, instant rollback by repointing active model_version; backtest on historical score partitions. Integrity: scoring package cannot import billing; scores table read-only except scoring worker. Full: /docs/03 (I) + /docs/04 (5).

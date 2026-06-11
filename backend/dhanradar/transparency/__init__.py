"""
DhanRadar — Data Transparency & Explainability module (Plan Group 9 / PU2).

Read-only surface: answers "how confident is this read, what data is it based on,
how fresh is it, and — when we won't score — says so openly."

Lane rules:
  * Reads persisted tables only (mf.user_fund_scores, mf.mf_nav_history,
    mf.mf_user_holdings, mf.mf_funds, mf.mf_portfolios). Zero writes.
  * Never imports from or modifies: scoring/engine/*, mf/signals.py,
    mf/scoring_bridge.py, mf/service.py, tasks/*, news/*, insights/*.
  * unified_score is never SELECTed or returned. Confidence BAND only.
  * Disclosure constants imported read-only from scoring/engine/schemas.py
    (B56-f1: do NOT create a third copy; defer move to shared module).
"""

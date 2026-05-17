"""
DhanRadar — Mood queue tasks.

Routed to the 'mood' queue via celery_app.conf.task_routes.
Populated in Phase 4 with sentiment analysis / news-mood scoring.
"""

from __future__ import annotations

from dhanradar.celery_app import celery_app


@celery_app.task(name="dhanradar.tasks.mood.run_sentiment_analysis")
def run_sentiment_analysis(symbol: str | None = None) -> str:
    """
    Stub: run sentiment analysis for market news / social signals.
    TODO Phase 4: implement OpenRouter-powered sentiment pipeline.
    """
    return f"sentiment_analysis: stub — symbol={symbol!r} not yet implemented"

"""
DhanRadar — Batch queue tasks.

Routed to the 'batch' queue via celery_app.conf.task_routes.
Populated in Phase 3+ with NAV ingestion, score computation, etc.
"""

from __future__ import annotations

from dhanradar.celery_app import celery_app


@celery_app.task(name="dhanradar.tasks.batch.run_nav_ingestion")
def run_nav_ingestion() -> str:
    """
    Stub: ingest daily NAV data for mutual funds and ETFs.
    TODO Phase 3: implement AMFI / exchange data fetch + TimescaleDB write.
    """
    return "nav_ingestion: stub — not yet implemented"

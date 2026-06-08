"""Regression test: the Celery WORKER must register every task module.

Production incident (2026-06-08): `autodiscover_tasks(["dhanradar.tasks"])`
resolved to the non-existent module `dhanradar.tasks.tasks` (package +
default related_name='tasks'), and `tasks/__init__.py` is empty, so the worker
imported ZERO task modules. Every enqueued task (CAS parse, NAV backfill,
notify-drain, mood) was received as an *unregistered task* and silently
discarded — CAS jobs hung forever at status='queued'.

This test mirrors exactly what a worker does on boot
(`import_default_modules()`) and asserts the canonical task names are
registered. CI green did not catch the incident because the suite invokes task
*functions* directly, never a live worker consuming from the broker.
"""

from __future__ import annotations

from dhanradar.celery_app import celery_app

# One representative task name per module (all five modules must load).
EXPECTED_TASKS = {
    "dhanradar.tasks.mf.parse_cas_job",
    "dhanradar.tasks.mf.nav_backfill",
    "dhanradar.tasks.mf.nav_daily_fetch",
    "dhanradar.tasks.mf.monthly_rescore_plus_users",
    "dhanradar.tasks.mf.purge_cas_files",
    "dhanradar.tasks.batch.run_nav_ingestion",
    "dhanradar.tasks.compliance.archive_audit_daily",
    "dhanradar.tasks.compliance.reconcile_audit_disclaimers",
    "dhanradar.tasks.misc.drain_notifications",
    "dhanradar.tasks.misc.send_notification",
    "dhanradar.tasks.mood.compute_mood_snapshot",
}


def test_worker_registers_every_task_module():
    # What `celery -A dhanradar.celery_app worker` does at boot.
    celery_app.loader.import_default_modules()
    registered = set(celery_app.tasks.keys())
    missing = EXPECTED_TASKS - registered
    assert not missing, (
        "Celery worker would DISCARD these as unregistered tasks "
        f"(jobs hang forever): {sorted(missing)}"
    )


def test_beat_schedule_tasks_are_registered():
    """Every task referenced by the beat schedule must be registered, or beat
    will send messages that workers discard."""
    celery_app.loader.import_default_modules()
    registered = set(celery_app.tasks.keys())
    scheduled = {
        entry["task"] for entry in celery_app.conf.beat_schedule.values()
    }
    missing = scheduled - registered
    assert not missing, f"Beat schedules unregistered tasks: {sorted(missing)}"

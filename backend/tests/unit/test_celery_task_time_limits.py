"""Regression test: EVERY celery task has a bounded soft/hard time limit.

Incident (2026-07-08): no task_time_limit/soft_time_limit existed anywhere in
celery_app.py — a scraper task hung mid-run with zero progress for 20+ minutes
and nothing detected or recovered it. Worse, a plain-dict `task_annotations =
{'*': {...}, 'task_name': {...}}` config was tried first and silently did NOT
work: Celery's own annotation resolution (celery/app/annotations.py
`resolve_all` + `Task.annotate()`) always applies the '*' wildcard match AFTER
the task-specific match and both are applied via plain `setattr`, so the
wildcard UNCONDITIONALLY overwrote every task-specific override sharing the
same keys — every task silently fell back to the global default regardless of
any per-task entry. See celery_app.py::_TaskTimeLimits for the fix (a custom
annotation object implementing only `annotate()`, no `annotate_any()`, so
Celery never resolves/applies a second competing value).

This test asserts against REAL resolved task attributes (via
`celery_app.finalize()` + `import_default_modules()`, mirroring what a worker
does on boot) — never against the config dict/class directly — so a
regression to the plain-dict form (or any future change that reintroduces the
clobbering bug) fails immediately.
"""

from __future__ import annotations

from dhanradar.celery_app import celery_app


def _finalized_task(name: str):
    celery_app.loader.import_default_modules()
    celery_app.finalize()
    task = celery_app.tasks.get(name)
    assert task is not None, f"{name} is not registered"
    return task


def test_every_registered_task_has_a_bounded_time_limit():
    """No task may have an unbounded (None) hard time_limit — the whole point
    of this fix is that NOTHING can hang forever, regardless of which
    scraper/extractor/task it is."""
    celery_app.loader.import_default_modules()
    celery_app.finalize()
    unbounded = [
        name
        for name, task in celery_app.tasks.items()
        if not name.startswith("celery.")  # built-in bookkeeping tasks, not ours
        and task.time_limit is None
    ]
    assert not unbounded, f"These tasks have NO hard time_limit (can hang forever): {unbounded}"


def test_fast_bucket_task_gets_the_tight_limit_not_the_global_default():
    """The exact regression this incident hit: a task explicitly listed in the
    fast bucket must resolve to the tight 4/5-min limit, NOT silently fall
    back to the 25/30-min global default."""
    task = _finalized_task("dhanradar.tasks.mf.mf_metrics_refresh")
    assert task.soft_time_limit == 240
    assert task.time_limit == 300


def test_reaper_tasks_get_the_tight_limit():
    """Reapers exist specifically to unblock other stuck work — they can never
    be allowed to become the next thing blocking the single-concurrency queue."""
    for name in (
        "dhanradar.tasks.mf.reap_stuck_cas_jobs",
        "dhanradar.tasks.manual_ingest.reap_stuck_manual_ingest_files",
    ):
        task = _finalized_task(name)
        assert task.time_limit <= 300, f"{name} time_limit={task.time_limit} is not tightly bounded"


def test_unlisted_scraper_task_gets_the_global_default():
    """A multi-source scraper NOT in the fast bucket must get the generous
    25/30-min default — never the tight 4/5-min bucket, which would kill a
    legitimate multi-AMC scrape partway through."""
    task = _finalized_task("dhanradar.tasks.mf.mf_constituents_fetch")
    assert task.soft_time_limit == 1500
    assert task.time_limit == 1800


def test_nav_backfill_gets_the_long_running_override():
    """The rare, manual, multi-year historical backfill needs far more headroom
    than the global default — it must not be killed partway through a
    legitimate long run."""
    task = _finalized_task("dhanradar.tasks.mf.nav_backfill")
    assert task.soft_time_limit == 6300
    assert task.time_limit == 6600


def test_every_fast_bucket_task_name_is_actually_registered():
    """Catches the inverse mistake: a typo'd or stale task name in the fast
    bucket that silently matches nothing (celery.app.annotations does not
    error on an unmatched name — it just never applies)."""
    from dhanradar.celery_app import _FAST_BUCKET_TASKS

    celery_app.loader.import_default_modules()
    registered = set(celery_app.tasks.keys())
    missing = _FAST_BUCKET_TASKS - registered
    assert not missing, f"Fast-bucket task names not registered (typo?): {sorted(missing)}"

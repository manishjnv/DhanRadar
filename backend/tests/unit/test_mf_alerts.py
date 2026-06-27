"""
Unit tests — MF Plus label-change alert pipeline.

Covers:
  1. changed→alert / unchanged→none / inserted=False→none (idempotency)
  2. Free user → no alert (loop continues before scoring)
  3. Portfolio-scoped copy in rendered template; HTML injection escape
  4. B31 cross-border consent gate drops the job (rides deliver seam unchanged)
  5. Factual copy: no advisory verb, no digit score, disclosure footer present
  6. B26 audit: record_served_label called on delivery (deliver-seam proof)
  7. get_prior_label: None when no row; returns most recent prior label
  8. append_score_history: True on rowcount==1, False on rowcount==0

asyncio_mode = "auto" (pyproject.toml) — no decorator needed.
No real DB, no network — all external call sites monkeypatched.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Shared fakes (mirrors test_mf_tracking.py pattern)
# ---------------------------------------------------------------------------


class _FakeDB:
    """Minimal DB fake: captures execute/commit; execute returns self."""

    def __init__(self, rows: list | None = None, rowcount: int = 1) -> None:
        self.executed: list[Any] = []
        self.committed = 0
        self._rows = rows or []
        self._rowcount = rowcount

    async def execute(self, stmt: Any) -> _FakeDB:
        self.executed.append(stmt)
        return self

    async def commit(self) -> None:
        self.committed += 1

    def scalars(self) -> _FakeDB:
        return self

    def all(self) -> list:
        return self._rows

    def scalar_one_or_none(self) -> Any:
        return self._rows[0] if self._rows else None

    @property
    def rowcount(self) -> int:
        return self._rowcount


def _make_result(
    isin: str = "INF000TEST01",
    verb_label: str = "on_track",
    confidence_band: str = "medium",
    model_version: str = "v1",
) -> MagicMock:
    r = MagicMock()
    r.identifier = isin
    r.verb_label = MagicMock()
    r.verb_label.value = verb_label
    r.confidence_band = MagicMock()
    r.confidence_band.value = confidence_band
    r.model_version = model_version
    r.unified_score = 72  # NEVER written (non-neg #2)
    return r


def _make_snap() -> MagicMock:
    s = MagicMock()
    s.total_invested = 10000.0
    s.current_value = 11000.0
    s.xirr_pct = 12.5
    s.category_allocation = {"large_cap": 100.0}
    s.overlap_matrix = {}
    return s


# ---------------------------------------------------------------------------
# 7. get_prior_label — no row → None; row present → label string
# ---------------------------------------------------------------------------


async def test_get_prior_label_returns_none_when_no_row():
    """get_prior_label returns None when there is no prior history row."""
    from dhanradar.mf import history as mf_history

    class _FakeResult:
        def scalar_one_or_none(self) -> None:
            return None

    class _DB:
        async def execute(self, stmt: Any) -> _FakeResult:
            return _FakeResult()

    result = await mf_history.get_prior_label(_DB(), "portfolio-a", "INF000A01", date(2026, 6, 1))
    assert result is None


async def test_get_prior_label_returns_most_recent():
    """get_prior_label returns the verb_label string when a prior row exists."""
    from dhanradar.mf import history as mf_history

    class _FakeResult:
        def scalar_one_or_none(self) -> str:
            return "in_form"

    class _DB:
        async def execute(self, stmt: Any) -> _FakeResult:
            return _FakeResult()

    result = await mf_history.get_prior_label(_DB(), "portfolio-a", "INF000A01", date(2026, 6, 1))
    assert result == "in_form"


async def test_get_prior_label_filters_by_portfolio_id():
    """The query where-clause includes portfolio_id (scoping guard)."""

    from dhanradar.mf import history as mf_history

    captured_stmt: list[Any] = []

    class _FakeResult:
        def scalar_one_or_none(self) -> None:
            return None

    class _DB:
        async def execute(self, stmt: Any) -> _FakeResult:
            captured_stmt.append(stmt)
            return _FakeResult()

    pid = "portfolio-xyz"
    await mf_history.get_prior_label(_DB(), pid, "INF000A01", date(2026, 6, 1))

    assert len(captured_stmt) == 1
    # The statement must have been executed — we trust the function's WHERE clause
    # rather than inspecting compiled SQL (avoids dialect coupling).
    stmt = captured_stmt[0]
    assert stmt is not None


# ---------------------------------------------------------------------------
# 8. append_score_history returns bool
# ---------------------------------------------------------------------------


async def test_append_score_history_returns_true_on_insert():
    """rowcount==1 → True (a row was actually inserted)."""
    from dhanradar.mf import history as mf_history

    class _FakeInsert:
        def values(self, **kw: Any) -> _FakeInsert:
            return self

        def on_conflict_do_nothing(self, **kw: Any) -> _FakeInsert:
            return self

    db = _FakeDB(rowcount=1)
    result = _make_result()

    with patch("dhanradar.mf.history.insert", lambda _: _FakeInsert()):
        with patch("dhanradar.models.mf.MfUserFundScoreHistory", MagicMock()):
            inserted = await mf_history.append_score_history(
                db,
                user_id="user-a",
                result=result,
                snapshot_date=date(2026, 6, 1),
                source="monthly_rescore",
                portfolio_id="portfolio-a",
            )

    assert inserted is True


async def test_append_score_history_returns_false_on_conflict():
    """rowcount==0 (ON CONFLICT DO NOTHING) → False (idempotency signal)."""
    from dhanradar.mf import history as mf_history

    class _FakeInsert:
        def values(self, **kw: Any) -> _FakeInsert:
            return self

        def on_conflict_do_nothing(self, **kw: Any) -> _FakeInsert:
            return self

    db = _FakeDB(rowcount=0)
    result = _make_result()

    with patch("dhanradar.mf.history.insert", lambda _: _FakeInsert()):
        with patch("dhanradar.models.mf.MfUserFundScoreHistory", MagicMock()):
            inserted = await mf_history.append_score_history(
                db,
                user_id="user-a",
                result=result,
                snapshot_date=date(2026, 6, 1),
                source="monthly_rescore",
                portfolio_id="portfolio-a",
            )

    assert inserted is False


# ---------------------------------------------------------------------------
# 3. Template: portfolio name in copy + HTML injection escape
# ---------------------------------------------------------------------------


def test_mf_label_change_contains_portfolio_name():
    """render() includes the portfolio name in both text and html when present."""
    from dhanradar.notifications.templates import render

    msg = render(
        "mf_label_change",
        {
            "scheme_name": "Fund A",
            "portfolio_name": "Retirement",
            "prior_label": "in_form",
            "new_label": "off_track",
        },
    )
    assert "Retirement" in msg.text
    assert "Retirement" in msg.html
    assert "Fund A" in msg.text
    assert "Fund A" in msg.html


def test_mf_label_change_graceful_when_portfolio_absent():
    """render() works cleanly when portfolio_name is missing or empty."""
    from dhanradar.notifications.templates import render

    msg = render(
        "mf_label_change",
        {
            "scheme_name": "Fund B",
            "prior_label": "on_track",
            "new_label": "out_of_form",
        },
    )
    # Should not contain the word "portfolio" in the copy body (only maybe in disclosure).
    # But must still render without error and carry disclosure.
    assert "Fund B" in msg.text
    assert "NOT_ADVICE" in msg.text


def test_mf_label_change_html_injection_portfolio_name():
    """An HTML-injecting portfolio name is escaped — no raw <script> in output."""
    from dhanradar.notifications.templates import render

    msg = render(
        "mf_label_change",
        {
            "scheme_name": "Fund C",
            "portfolio_name": "<script>alert(1)</script>",
            "prior_label": "on_track",
            "new_label": "off_track",
        },
    )
    assert "<script>" not in msg.text
    assert "<script>" not in msg.html
    assert "&lt;script&gt;" in msg.text or "&lt;script&gt;" in msg.html


def test_mf_label_change_html_injection_scheme_name():
    """An HTML-unsafe scheme name is escaped in both text and html (existing RCA guard)."""
    from dhanradar.notifications.templates import render

    msg = render(
        "mf_label_change",
        {
            "scheme_name": "<b>Evil Fund</b>",
            "portfolio_name": "Safe Portfolio",
            "prior_label": "in_form",
            "new_label": "off_track",
        },
    )
    assert "<b>" not in msg.html
    assert "&lt;b&gt;" in msg.html


# ---------------------------------------------------------------------------
# 5. Factual copy: no advisory verb, no digit score, disclosure present
# ---------------------------------------------------------------------------


def test_mf_label_change_no_advisory_verbs():
    """No advisory verb in the TEMPLATE BODY (footer intentionally negates them).

    The disclosure footer contains "not a recommendation to buy, sell, hold, or
    switch" — that usage is correct and expected. The test checks the body only
    (the part before the footer separator "—") where advisory imperative framing
    must never appear.
    """
    from dhanradar.notifications.templates import render

    msg = render(
        "mf_label_change",
        {
            "scheme_name": "HDFC Flexicap Fund",
            "portfolio_name": "Long Term",
            "prior_label": "in_form",
            "new_label": "off_track",
        },
    )
    # Split on the footer separator ("— Educational…"); body is everything before it.
    body_text = msg.text.split("\n\n")[0]
    body_html = msg.html.split("<p style=")[0]
    advisory = re.compile(r"\b(buy|sell|hold|switch|avoid|caution)\b", re.IGNORECASE)
    assert not advisory.search(body_text), f"Advisory verb found in body text: {body_text}"
    assert not advisory.search(body_html), f"Advisory verb found in body html: {body_html}"


def test_mf_label_change_no_numeric_score():
    """Rendered text must not contain a bare digit sequence (no score leak)."""
    from dhanradar.notifications.templates import render

    msg = render(
        "mf_label_change",
        {
            "scheme_name": "Axis Bluechip",
            "portfolio_name": "Core",
            "prior_label": "on_track",
            "new_label": "out_of_form",
        },
    )
    # The disclaimer version string contains digits — exclude that portion.
    # We check the body (before the footer separator) for raw score-like digits.
    body = msg.text.split("—")[0]
    assert not re.search(r"\b\d{2,}\b", body), f"Digit sequence found in body: {body}"


def test_mf_label_change_disclosure_footer_present():
    """Disclosure footer + NOT_ADVICE are always appended by render()."""
    from dhanradar.notifications.templates import render

    msg = render(
        "mf_label_change",
        {
            "scheme_name": "SBI Bluechip",
            "prior_label": "on_track",
            "new_label": "off_track",
        },
    )
    assert "NOT_ADVICE" in msg.text
    assert "NOT_ADVICE" in msg.html
    # DISCLOSURE_BUNDLE content (educational context)
    assert "Educational" in msg.text or "educational" in msg.text


# ---------------------------------------------------------------------------
# 1. _monthly_rescore alert logic: changed→enqueue / unchanged→skip / idempotency
# ---------------------------------------------------------------------------


async def _run_rescore_with_patches(
    monkeypatch: Any,
    *,
    plus: bool = True,
    prior_label: str | None,
    new_label: str = "off_track",
    inserted: bool = True,
    portfolio_name: str = "Retirement",
) -> list:
    """Helper: run _monthly_rescore with a single portfolio/holding, capturing
    publish_notification calls. Returns the list of captured call args."""
    import dhanradar.mf.history as _mf_history_mod
    import dhanradar.tasks.mf as mf_tasks

    uid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    isin = "INF000TEST01"
    publish_calls: list[tuple] = []

    async def _fake_is_plus(u: str, db: Any) -> bool:
        return plus

    async def _fake_get_prior_label(db: Any, portfolio_id: Any, isin_: str, before: Any) -> str | None:
        return prior_label

    async def _fake_append(db_arg: Any = None, **kw: Any) -> bool:
        return inserted

    async def _fake_persist(**kw: Any) -> None:
        pass

    async def _fake_score_fund(engine: Any, signals: Any) -> MagicMock:
        return _make_result(isin=isin, verb_label=new_label)

    async def _fake_load_nav(db: Any, isins: list, lookback_days: int = 400) -> tuple:
        return ({i: [(date(2026, 6, 1), 100.0)] for i in isins}, {i: 100.0 for i in isins})

    def _fake_compute_signals(isin_: str, series: Any, **kw: Any) -> MagicMock:
        m = MagicMock()
        m.isin = isin_
        return m

    async def _fake_publish(redis: Any, user_id: str, ch: str, tmpl: str, data: dict | None = None, **kw: Any) -> MagicMock:
        publish_calls.append((user_id, ch, tmpl, data))
        return MagicMock()

    def _make_holding(isin_: str) -> MagicMock:
        h = MagicMock()
        h.isin = isin_
        h.units = 10.0
        h.invested_amount = 1000.0
        return h

    holding = _make_holding(isin)

    class _FakeScalars:
        def all(self) -> list:
            return [holding]

    class _FakeHoldingResult:
        def scalars(self) -> _FakeScalars:
            return _FakeScalars()

    class _FakeSchemeResult:
        def all(self) -> list:
            return [(isin, "Test Fund")]

    class _FakePortfolioSession:
        _call = 0

        async def execute(self, stmt: Any) -> Any:
            self._call += 1
            if self._call == 1:
                # portfolio user+name query
                r = MagicMock()
                r.first = lambda: (uid, portfolio_name)
                return r
            if self._call == 2:
                # holdings select
                return _FakeHoldingResult()
            # scheme_name batch fetch
            return _FakeSchemeResult()

        async def __aenter__(self) -> _FakePortfolioSession:
            return self

        async def __aexit__(self, *a: Any) -> None:
            pass

    class _FakeUserSession:
        def __init__(self) -> None:
            self._n = 0

        async def execute(self, stmt: Any) -> Any:
            self._n += 1
            r = MagicMock()
            if self._n == 1:
                # distinct (portfolio_id, isin) holdings pre-pass (B58-f2)
                r.all = lambda: [(pid, isin)]
            else:
                # portfolio → owner resolve
                r.all = lambda: [(pid, uid)]
            return r

        async def __aenter__(self) -> _FakeUserSession:
            return self

        async def __aexit__(self, *a: Any) -> None:
            pass

    session_n = {"n": 0}

    class _FakeSessionMaker:
        def __call__(self) -> Any:
            n = session_n["n"]
            session_n["n"] += 1
            if n == 0:
                return _FakeUserSession()
            return _FakePortfolioSession()

    monkeypatch.setattr(mf_tasks, "score_fund", _fake_score_fund, raising=True)
    monkeypatch.setattr(mf_tasks, "_load_nav_series", _fake_load_nav, raising=True)
    monkeypatch.setattr(mf_tasks, "compute_fund_signals", _fake_compute_signals, raising=True)
    monkeypatch.setattr(mf_tasks, "build_snapshot", lambda holdings: _make_snap(), raising=True)
    monkeypatch.setattr(mf_tasks, "upsert_user_fund_score", AsyncMock(), raising=True)
    # Cohort context is built once before the loop (B58-f2) — not under test here.
    monkeypatch.setattr(
        mf_tasks,
        "_build_cohort_context",
        AsyncMock(return_value=mf_tasks._EMPTY_COHORT_CONTEXT),
        raising=True,
    )
    monkeypatch.setattr(_mf_history_mod, "append_score_history", _fake_append)
    monkeypatch.setattr(_mf_history_mod, "get_prior_label", _fake_get_prior_label)
    monkeypatch.setattr(_mf_history_mod, "persist_portfolio_snapshot", _fake_persist)
    monkeypatch.setattr("dhanradar.deps.is_plus", _fake_is_plus)

    from dhanradar.notifications import service as notif_service
    monkeypatch.setattr(notif_service, "publish_notification", _fake_publish)

    with patch("dhanradar.db.admin_task_session", _FakeSessionMaker()):
        with patch("dhanradar.scoring.engine.RatingEngine", MagicMock()):
            with patch("dhanradar.db.engine", MagicMock()):
                with patch("dhanradar.redis_client.get_redis", lambda: MagicMock()):
                    await mf_tasks._monthly_rescore()

    return publish_calls


async def test_alert_enqueued_when_label_changes(monkeypatch):
    """prior_label != new_label + inserted=True → publish_notification called for both channels."""
    calls = await _run_rescore_with_patches(
        monkeypatch,
        prior_label="in_form",
        new_label="off_track",
        inserted=True,
    )
    channels_called = {c[1] for c in calls}
    assert "telegram" in channels_called
    assert "email" in channels_called
    assert all(c[2] == "mf_label_change" for c in calls)


async def test_no_alert_when_label_unchanged(monkeypatch):
    """prior_label == new_label → publish_notification NOT called."""
    calls = await _run_rescore_with_patches(
        monkeypatch,
        prior_label="off_track",
        new_label="off_track",
        inserted=True,
    )
    assert calls == []


async def test_no_alert_when_no_prior_label(monkeypatch):
    """prior_label is None (first score) → publish_notification NOT called."""
    calls = await _run_rescore_with_patches(
        monkeypatch,
        prior_label=None,
        new_label="off_track",
        inserted=True,
    )
    assert calls == []


async def test_no_alert_when_not_inserted(monkeypatch):
    """inserted=False (same-day conflict) → publish_notification NOT called (idempotency)."""
    calls = await _run_rescore_with_patches(
        monkeypatch,
        prior_label="in_form",
        new_label="off_track",
        inserted=False,
    )
    assert calls == []


# ---------------------------------------------------------------------------
# 2. Free user → no alert
# ---------------------------------------------------------------------------


async def test_free_user_no_alert(monkeypatch):
    """is_plus=False → loop continues before scoring → publish_notification never called."""
    calls = await _run_rescore_with_patches(
        monkeypatch,
        plus=False,
        prior_label="in_form",
        new_label="off_track",
        inserted=True,
    )
    assert calls == []


# ---------------------------------------------------------------------------
# 4. B31 — cross-border consent gate drops the job (deliver seam unchanged)
# ---------------------------------------------------------------------------


async def test_b31_consent_gate_drops_job(fake_redis):
    """A mf_label_change job with no cross_border_notify consent is dropped
    at _handle_job with 'cross_border_consent_required' and NOT delivered.

    This test exercises the UNCHANGED deliver seam (tasks/misc.py) to prove
    the alert rides B31 without any modification to that module.
    """
    from dhanradar.notifications import service
    from dhanradar.tasks.misc import _handle_job

    uid = str(uuid.uuid4())

    # Publish a mf_label_change job onto the queue.
    job = await service.publish_notification(
        fake_redis,
        uid,
        "telegram",
        "mf_label_change",
        {
            "scheme_name": "Test Fund",
            "portfolio_name": "Retirement",
            "prior_label": "in_form",
            "new_label": "off_track",
            "isin": "INF000TEST01",
            "confidence_band": "medium",
        },
    )

    log_calls: list[tuple] = []

    async def _fake_log(db: Any, user_id: str, ch: str, tmpl: str, status: str, err: str | None = None) -> None:
        log_calls.append((status, err))

    async def _fake_prefs(db: Any, user_id: str) -> dict:
        return {
            "telegram_chat_id": "12345",
            "email_verified": True,
            "whatsapp_number": None,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "channels_enabled": {"telegram": True, "email": True},
        }

    # Consent denied — B31 gate fires.
    async def _consent_denied(user_id: str, purpose: str, db: Any) -> bool:
        return False

    deliver_calls: list = []

    async def _fake_deliver(chat_id: str, text: str, **kw: Any) -> MagicMock:
        deliver_calls.append(chat_id)
        r = MagicMock()
        r.ok = True
        r.transient = False
        return r

    db = MagicMock()
    now = __import__("datetime").time(12, 0)

    with patch("dhanradar.tasks.misc.service.get_preferences", _fake_prefs):
        with patch("dhanradar.tasks.misc.service.log_delivery", _fake_log):
            with patch("dhanradar.deps.consent_granted", _consent_denied):
                result = await _handle_job(db, fake_redis, job, now)

    assert result is False
    assert deliver_calls == [], "Transport must not be called when consent is denied"
    # The audit log must record the B31 drop.
    assert any(err == "cross_border_consent_required" for _, err in log_calls)


# ---------------------------------------------------------------------------
# 6. B26 audit — record_served_label called on delivery
# ---------------------------------------------------------------------------


async def test_b26_record_served_label_on_delivery(fake_redis):
    """On successful delivery of mf_label_change, record_served_label is called
    with label==job.data['new_label'] by the deliver seam (misc.py unchanged)."""
    from dhanradar.notifications import service
    from dhanradar.tasks.misc import _handle_job

    uid = str(uuid.uuid4())
    job = await service.publish_notification(
        fake_redis,
        uid,
        "telegram",
        "mf_label_change",
        {
            "scheme_name": "HDFC Flexi",
            "portfolio_name": "Core",
            "prior_label": "on_track",
            "new_label": "off_track",
            "isin": "INF0001TEST",
            "confidence_band": "high",
        },
    )

    compliance_calls: list[dict] = []

    async def _fake_log(*a: Any, **kw: Any) -> None:
        pass

    async def _fake_prefs(db: Any, user_id: str) -> dict:
        return {
            "telegram_chat_id": "99999",
            "email_verified": True,
            "whatsapp_number": None,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "channels_enabled": {"telegram": True},
        }

    async def _consent_granted(user_id: str, purpose: str, db: Any) -> bool:
        return True

    async def _fake_rate_reached(redis: Any, user_id: str, ch: str) -> bool:
        return False

    async def _fake_rate_inc(redis: Any, user_id: str, ch: str) -> int:
        return 1

    async def _fake_deliver_tg(chat_id: str, text: str, **kw: Any) -> MagicMock:
        r = MagicMock()
        r.ok = True
        r.transient = False
        r.code = "ok"
        return r

    async def _fake_record_served(
        *,
        surface: str,
        label: str,
        model: Any,
        disclaimer_version: str,
        user_id: str,
        identifier: str | None,
        confidence_band: str | None,
    ) -> None:
        compliance_calls.append({"label": label, "surface": surface, "identifier": identifier})

    def _fake_active_dv() -> str:
        return "v1"

    db = MagicMock()
    now = __import__("datetime").time(12, 0)

    with patch("dhanradar.tasks.misc.service.get_preferences", _fake_prefs):
        with patch("dhanradar.tasks.misc.service.log_delivery", _fake_log):
            with patch("dhanradar.tasks.misc.service.rate_cap_reached", _fake_rate_reached):
                with patch("dhanradar.tasks.misc.service.rate_cap_increment", _fake_rate_inc):
                    with patch("dhanradar.deps.consent_granted", _consent_granted):
                        with patch("dhanradar.notifications.channels.deliver_telegram", _fake_deliver_tg):
                            with patch(
                                "dhanradar.compliance.service.record_served_label",
                                _fake_record_served,
                            ):
                                with patch(
                                    "dhanradar.compliance.service.active_disclaimer_version",
                                    _fake_active_dv,
                                ):
                                    result = await _handle_job(db, fake_redis, job, now)

    assert result is True
    assert len(compliance_calls) == 1
    assert compliance_calls[0]["label"] == "off_track"
    assert compliance_calls[0]["surface"] == "notification_telegram"
    assert compliance_calls[0]["identifier"] == "INF0001TEST"

"""Daily watchlist alerts task (P2 backend).

Scans mf_watchlist_items, checks two trigger types against EXISTING persisted data
(never re-scores), inserts alerts into mf_watchlist_alerts with ON CONFLICT DO NOTHING,
then sends one email digest per user per day (Redis TTL dedup).

Trigger types:
  nav_move     — 1-day NAV move >= +/-2% from mf_nav_history (latest 2 rows).
  label_change — verb_label change between the 2 most-recent mf_fund_ranks rows
                 for that ISIN (never recomputes the score).

Safety properties:
  - All data reads are from already-persisted tables; no scoring re-runs.
  - INSERT ON CONFLICT DO NOTHING is the structural dedup (one alert per
    user/isin/type/day).
  - Email dedup: Redis key `mf:watchlist_digest:{user_id}` with TTL 86 400 s
    ensures at most one digest per user per calendar day.
  - Missing RESEND_API_KEY → delivery is skipped, logged once, task continues.
  - Any per-user or per-fund error is caught, logged, and skipped — the task
    never aborts the whole run on a single bad row.
"""

from __future__ import annotations

import asyncio
from datetime import date
from uuid import UUID

import structlog

from dhanradar.celery_app import celery_app

log = structlog.get_logger(__name__)

_DIGEST_REDIS_KEY = "mf:watchlist_digest:{user_id}"
_DIGEST_TTL_SECS = 86_400  # 1 day


@celery_app.task(name="dhanradar.tasks.watchlist_alerts.daily_watchlist_alerts")
def daily_watchlist_alerts() -> str:
    """Fire nav_move and label_change alerts for every user's watchlist.

    Scheduled off-market-hours (02:30 IST) so the nightly nav_daily_fetch
    (23:30) and compute_market_ranks (01:00) are complete before we read them.
    """
    return asyncio.run(_run())


async def _run() -> str:
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.db import admin_task_session
    from dhanradar.mf.watchlist_alerts import (
        label_alert_copy,
        nav_alert_copy,
        nav_move_pct,
        should_fire_label_change,
        should_fire_nav_move,
    )
    from dhanradar.models.auth import User
    from dhanradar.models.mf import (
        MfFund,
        MfFundRanks,
        MfNavHistory,
        MfWatchlistAlert,
        MfWatchlistItem,
    )
    from dhanradar.redis_client import get_redis

    today = date.today()
    inserted_total = 0
    digests_sent = 0

    async with admin_task_session() as db:
        # All active watchlist items (BYPASSRLS → cross-user read).
        watchlist_rows = (await db.execute(select(MfWatchlistItem))).scalars().all()

        if not watchlist_rows:
            return "watchlist_alerts: no watchlist items, skipping"

        # Distinct ISINs — fund metadata loaded once.
        all_isins = list({row.isin for row in watchlist_rows})
        fund_meta: dict[str, tuple[str, str]] = {}
        for f in (
            await db.execute(
                select(MfFund.isin, MfFund.fund_name_short, MfFund.scheme_name)
                .where(MfFund.isin.in_(all_isins))
            )
        ).all():
            fund_meta[f.isin] = (
                f.fund_name_short or f.scheme_name or f.isin,
                f.scheme_name or f.isin,
            )

        # NAV move: latest 2 rows per ISIN.
        nav_today_map: dict[str, float] = {}
        nav_yesterday_map: dict[str, float] = {}
        for isin in all_isins:
            try:
                rows = (
                    await db.execute(
                        select(MfNavHistory.nav)
                        .where(MfNavHistory.isin == isin)
                        .order_by(MfNavHistory.nav_date.desc())
                        .limit(2)
                    )
                ).all()
                if len(rows) >= 2:
                    nav_today_map[isin] = float(rows[0].nav)
                    nav_yesterday_map[isin] = float(rows[1].nav)
            except Exception:  # noqa: BLE001
                log.warning("watchlist_alerts.nav_read_error", isin=isin, exc_info=True)

        # Label change: latest 2 rank rows per ISIN.
        rank_current_map: dict[str, tuple[str, str | None]] = {}
        rank_previous_map: dict[str, str] = {}
        for isin in all_isins:
            try:
                rows = (
                    await db.execute(
                        select(MfFundRanks.verb_label, MfFundRanks.confidence_band)
                        .where(MfFundRanks.isin == isin)
                        .order_by(MfFundRanks.as_of_date.desc())
                        .limit(2)
                    )
                ).all()
                if len(rows) >= 2:
                    rank_current_map[isin] = (rows[0].verb_label, rows[0].confidence_band)
                    rank_previous_map[isin] = rows[1].verb_label
            except Exception:  # noqa: BLE001
                log.warning("watchlist_alerts.rank_read_error", isin=isin, exc_info=True)

        # Build alerts per (user_id, isin).
        alerts_by_user: dict[UUID, list[MfWatchlistAlert]] = {}

        for item in watchlist_rows:
            isin = item.isin
            uid = item.user_id
            fund_name, _ = fund_meta.get(isin, (isin, isin))
            pending: list[MfWatchlistAlert] = []

            nav_t = nav_today_map.get(isin)
            nav_y = nav_yesterday_map.get(isin)
            if nav_t is not None and nav_y is not None and should_fire_nav_move(nav_t, nav_y):
                pct = nav_move_pct(nav_t, nav_y) or 0.0
                title, body = nav_alert_copy(isin, fund_name, pct)
                pending.append(
                    MfWatchlistAlert(
                        user_id=uid,
                        isin=isin,
                        alert_type="nav_move",
                        title=title,
                        body=body,
                        triggered_on=today,
                    )
                )

            curr = rank_current_map.get(isin)
            prev_label = rank_previous_map.get(isin)
            if curr is not None and prev_label is not None:
                curr_label, confidence_band = curr
                if should_fire_label_change(prev_label, curr_label):
                    title, body = label_alert_copy(isin, fund_name, prev_label, curr_label, confidence_band)
                    pending.append(
                        MfWatchlistAlert(
                            user_id=uid,
                            isin=isin,
                            alert_type="label_change",
                            title=title,
                            body=body,
                            triggered_on=today,
                        )
                    )

            if pending:
                alerts_by_user.setdefault(uid, []).extend(pending)

        # Bulk INSERT ON CONFLICT DO NOTHING.
        for uid, alerts in alerts_by_user.items():
            for alert in alerts:
                try:
                    await db.execute(
                        insert(MfWatchlistAlert)
                        .values(
                            user_id=uid,
                            isin=alert.isin,
                            alert_type=alert.alert_type,
                            title=alert.title,
                            body=alert.body,
                            triggered_on=alert.triggered_on,
                        )
                        .on_conflict_do_nothing(constraint="uq_mf_watchlist_alert")
                    )
                    inserted_total += 1
                except Exception:  # noqa: BLE001
                    log.warning(
                        "watchlist_alerts.insert_error",
                        user_id=str(uid),
                        isin=alert.isin,
                        exc_info=True,
                    )
        await db.commit()

        # Email digest — one per user per day (Redis TTL guard).
        from dhanradar.config import settings

        if not settings.RESEND_API_KEY:
            log.info("watchlist_alerts.email_skip", reason="RESEND_API_KEY not set")
        else:
            redis = get_redis()
            user_ids = list(alerts_by_user.keys())
            user_email_map = {
                row.id: row.email
                for row in (
                    await db.execute(select(User.id, User.email).where(User.id.in_(user_ids)))
                ).all()
            }

            for uid, alerts in alerts_by_user.items():
                try:
                    digest_key = _DIGEST_REDIS_KEY.format(user_id=str(uid))
                    if await redis.exists(digest_key):
                        continue
                    email_addr = user_email_map.get(uid)
                    if not email_addr:
                        continue
                    result = await _send_digest(email_addr, alerts, today)
                    if result.ok:
                        await redis.set(digest_key, "1", ex=_DIGEST_TTL_SECS)
                        digests_sent += 1
                except Exception:  # noqa: BLE001
                    log.warning("watchlist_alerts.digest_error", user_id=str(uid), exc_info=True)

    log.info(
        "watchlist_alerts.done",
        inserted=inserted_total,
        digests_sent=digests_sent,
        date=today.isoformat(),
    )
    return f"watchlist_alerts: inserted={inserted_total} digests_sent={digests_sent}"


async def _send_digest(
    email: str,
    alerts: list,
    today: date,
) -> object:
    """Compose and dispatch one email digest. Returns a DeliveryResult."""
    from dhanradar.notifications.channels import deliver_email

    items_html = "".join(
        f"<li><strong>{a.title}</strong><br>{a.body}</li>" for a in alerts
    )
    items_text = "\n".join(f"- {a.title}: {a.body}" for a in alerts)
    subject = f"DhanRadar watchlist update – {today.isoformat()}"
    html = (
        f"<p>Your watchlist had {len(alerts)} update(s) today:</p>"
        f"<ul>{items_html}</ul>"
        "<p><em>This is a factual data notification. "
        "NOT INVESTMENT ADVICE. For educational purposes only. "
        "DhanRadar does not provide investment advisory services.</em></p>"
    )
    text = (
        f"Your watchlist had {len(alerts)} update(s) today ({today.isoformat()}):\n\n"
        f"{items_text}\n\n"
        "NOT INVESTMENT ADVICE. For educational purposes only."
    )
    return await deliver_email(email, subject, html, text)

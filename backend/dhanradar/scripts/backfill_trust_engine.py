"""
DhanRadar — Trust Engine Historical Backfill.

Computes what the signal state WOULD have been for every Nifty trading day over the
last 2 years, using historical Nifty + VIX data from Yahoo Finance, and writes the
rows into signal.signal_history.

Run ONCE after migration 0030 is applied:
    docker compose -p dhanradar exec dhanradar-fastapi \
        python -m dhanradar.scripts.backfill_trust_engine

The script is idempotent: duplicate dates are ignored (ON CONFLICT DO NOTHING).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

log = logging.getLogger(__name__)


def _nifty_score(pct: float) -> int:
    if pct > 0:
        return 0
    if pct > -2:
        return 1
    if pct > -5:
        return 2
    if pct > -8:
        return 3
    return 4


def _vix_score(v: float) -> int:
    if v < 15:
        return 0
    if v < 17:
        return 1
    if v < 19:
        return 2
    if v < 22:
        return 3
    return 4


def _breadth_score(ad: float) -> int:
    if ad > 1.5:
        return 0
    if ad > 1.2:
        return 1
    if ad > 0.8:
        return 2
    if ad > 0.5:
        return 3
    return 4


def _compute_signal_state(nifty_pct: float, vix: float, ad_ratio: float) -> str:
    weighted = (
        _nifty_score(nifty_pct) * 0.20
        + _vix_score(vix) * 0.40
        + _breadth_score(ad_ratio) * 0.40
    )
    if weighted >= 3.0:
        return "triggered"
    if weighted >= 2.0:
        return "watch"
    return "no_signal"


async def backfill() -> None:
    import yfinance as yf
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from dhanradar.db import TaskSessionLocal
    from dhanradar.signal.models import SignalHistory

    log.info("Fetching 2y Nifty + VIX history from Yahoo Finance…")
    nifty_series = yf.Ticker("^NSEI").history(period="2y")["Close"]
    vix_series = yf.Ticker("^INDIAVIX").history(period="2y")["Close"]

    if nifty_series.empty or vix_series.empty:
        log.error("Failed to fetch historical data — aborting backfill")
        return


    nifty_df = nifty_series.rename("nifty").to_frame()
    vix_df = vix_series.rename("vix").to_frame()
    merged = nifty_df.join(vix_df, how="inner").dropna()

    merged["nifty_pct"] = merged["nifty"].pct_change() * 100
    # Breadth proxy: positive Nifty day → A/D 1.5 (broad advance), negative → 0.6 (broad decline)
    merged["ad_ratio_proxy"] = merged["nifty_pct"].apply(lambda x: 1.5 if x > 0 else 0.6)
    merged = merged.dropna()

    today_date = date.today()
    dates_list = list(merged.index)
    rows_to_insert: list[dict] = []

    for i, idx in enumerate(dates_list):
        row_date: date = idx.date() if hasattr(idx, "date") else idx
        nifty_close = float(merged.at[idx, "nifty"])
        vix_close = float(merged.at[idx, "vix"])
        nifty_pct = float(merged.at[idx, "nifty_pct"])
        ad_ratio_proxy = float(merged.at[idx, "ad_ratio_proxy"])

        signal_state = _compute_signal_state(nifty_pct, vix_close, ad_ratio_proxy)

        # 90-day outcome: Nifty close on first trading day at or after (row_date + 90 days)
        outcome_pct_90d = None
        outcome_date = row_date + timedelta(days=90)
        if outcome_date <= today_date:
            future_closes = [
                float(merged.at[fut_idx, "nifty"])
                for fut_idx in dates_list[i + 1:]
                if (fut_idx.date() if hasattr(fut_idx, "date") else fut_idx) >= outcome_date
            ]
            if future_closes:
                outcome_pct_90d = round((future_closes[0] / nifty_close - 1) * 100, 4)

        rows_to_insert.append({
            "date": row_date,
            "signal_state": signal_state,
            "nifty_close": round(nifty_close, 2),
            "vix_close": round(vix_close, 2),
            "ad_ratio_proxy": round(ad_ratio_proxy, 3),
            "outcome_pct_90d": outcome_pct_90d,
        })

    log.info("Upserting %d signal history rows…", len(rows_to_insert))

    async with TaskSessionLocal() as db:
        stmt = (
            pg_insert(SignalHistory)
            .values(rows_to_insert)
            .on_conflict_do_nothing(constraint="uq_signal_history_date")
        )
        await db.execute(stmt)
        await db.commit()

    log.info("Backfill complete — %d rows processed", len(rows_to_insert))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    asyncio.run(backfill())


if __name__ == "__main__":
    main()

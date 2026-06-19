"""
DhanRadar — NIFTY-50 market breadth helper.

This module is the single authoritative location for the NIFTY-50 constituent
advances/declines fetch.  It lives in the ``market_data`` layer so that both
the ``mood`` layer (via ``_fetch_breadth_sync``) and the ``market_data``
``YahooMacroProvider`` pipeline can import it without a circular dependency —
``market_data`` is upstream of ``mood``.
"""

from __future__ import annotations

import logging
import time as _time_module

logger = logging.getLogger(__name__)

_NIFTY50_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "HCLTECH.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS",
    "NESTLEIND.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "M&M.NS",
    "TATAMOTORS.NS", "COALINDIA.NS", "TATASTEEL.NS", "GRASIM.NS", "ADANIPORTS.NS",
    "BAJAJ-AUTO.NS", "TECHM.NS", "DRREDDY.NS", "HINDALCO.NS", "CIPLA.NS",
    "SBILIFE.NS", "JSWSTEEL.NS", "BPCL.NS", "BAJAJFINSV.NS", "BRITANNIA.NS",
    "EICHERMOT.NS", "HDFCLIFE.NS", "APOLLOHOSP.NS", "INDUSINDBK.NS", "DIVISLAB.NS",
    "TATACONSUM.NS", "HEROMOTOCO.NS", "SHRIRAMFIN.NS", "BEL.NS", "ADANIENT.NS",
]


def fetch_nifty50_advances_declines_sync() -> tuple[int, int]:
    """Fetch NIFTY-50 constituent advances/declines counts from Yahoo Finance.

    Downloads 2 days of close prices for all 50 tickers and counts how many
    advanced (today close > prev close) vs declined.  Raises ``ValueError`` on
    insufficient data.  This is the single shared implementation used by both
    the Signal-card breadth path (``_fetch_breadth_sync``) and the
    ``YahooMacroProvider`` macro pipeline — no duplicated logic.

    Returns:
        (advances, declines): integer counts; advances + declines == valid tickers.
    """
    import yfinance as yf

    start = _time_module.monotonic()

    close_data = yf.download(
        _NIFTY50_TICKERS, period="2d", progress=False, auto_adjust=True
    )["Close"]

    if close_data.empty or len(close_data) < 2:
        raise ValueError("insufficient breadth data")

    today_row = close_data.iloc[-1]
    prev_row = close_data.iloc[-2]
    valid = today_row.notna() & prev_row.notna()
    advances = int((today_row[valid] > prev_row[valid]).sum())
    declines = int(valid.sum()) - advances
    declines = max(declines, 0)

    elapsed_ms = round((_time_module.monotonic() - start) * 1000)
    logger.info(
        "signal.breadth_fetch advances=%d declines=%d elapsed_ms=%d",
        advances, declines, elapsed_ms,
    )
    return advances, declines

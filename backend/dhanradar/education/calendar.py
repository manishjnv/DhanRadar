"""
DhanRadar — FY-aware Indian tax calendar (G8) — pure, deterministic from a date.

The Indian financial year (FY) runs 1 April – 31 March. This module derives the
current FY and the statutory key dates within it (advance-tax instalments, FY-end,
the usual income-tax-return due date for non-audit individuals). Everything is
GENERAL and EDUCATIONAL — described, never personalised, never advice. Dates can
change by government/CBDT notification; the FY label is always shown alongside.

Pure functions (a `today` is always passed in) so the FY boundary at 1 April is
deterministically testable.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

# India has no DST, so a fixed +5:30 offset is exact and needs no tzdata package.
_IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def today_ist() -> datetime.date:
    """Today's date in IST — the FY rolls over at midnight India time, not UTC, so
    the calendar must pivot on the IST date (else 00:00–05:30 IST on 1 April still
    shows the old FY to a UTC server)."""
    return datetime.datetime.now(_IST).date()


@dataclass(frozen=True)
class KeyDate:
    label: str
    date: datetime.date
    note: str


def current_fy(today: datetime.date) -> tuple[int, int]:
    """Return (start_year, end_year) of the Indian FY containing ``today``.

    The FY starts on 1 April. So 2026-03-31 → (2025, 2026) and 2026-04-01 →
    (2026, 2027) — the boundary that the calendar's key dates pivot on.
    """
    if today.month >= 4:
        return today.year, today.year + 1
    return today.year - 1, today.year


def fy_label(start_year: int, end_year: int) -> str:
    """Human label, e.g. ``FY 2025-26 (AY 2026-27)`` (AY = the assessment year)."""
    return (
        f"FY {start_year}-{str(end_year)[-2:]} "
        f"(AY {end_year}-{str(end_year + 1)[-2:]})"
    )


def build_tax_calendar(today: datetime.date) -> dict:
    """Build the current FY's statutory key-date calendar from ``today``.

    Returns a plain dict (the router wraps it with the disclosure bundle). All
    entries are general statutory dates described educationally — no personal data,
    no recommendation. Amounts shown as percentages are the cumulative advance-tax
    proportions defined in law, not a suggestion to pay.
    """
    start, end = current_fy(today)
    label = fy_label(start, end)

    key_dates = [
        KeyDate(
            "Advance tax — 1st instalment",
            datetime.date(start, 6, 15),
            "By 15 June: up to 15% of the year's estimated tax liability, where advance tax applies.",
        ),
        KeyDate(
            "Advance tax — 2nd instalment",
            datetime.date(start, 9, 15),
            "By 15 September: cumulatively up to 45% of the estimated liability, where it applies.",
        ),
        KeyDate(
            "Advance tax — 3rd instalment",
            datetime.date(start, 12, 15),
            "By 15 December: cumulatively up to 75% of the estimated liability, where it applies.",
        ),
        KeyDate(
            "Advance tax — 4th instalment",
            datetime.date(end, 3, 15),
            "By 15 March: cumulatively up to 100% of the estimated liability, where it applies.",
        ),
        KeyDate(
            "Financial year end",
            datetime.date(end, 3, 31),
            "Last day of the FY — the cut-off for tax-saving investments (such as Section 80C "
            "items under the old tax regime) to count in this year.",
        ),
        KeyDate(
            "Income-tax return — usual due date",
            datetime.date(end, 7, 31),
            "Typical due date for individuals not requiring an audit to file the return for this "
            "FY. The date is set each year by the CBDT and can change.",
        ),
    ]
    key_dates.sort(key=lambda d: d.date)

    return {
        "fy_label": label,
        "fy_start": datetime.date(start, 4, 1).isoformat(),
        "fy_end": datetime.date(end, 3, 31).isoformat(),
        "key_dates": [
            {"label": d.label, "date": d.date.isoformat(), "note": d.note} for d in key_dates
        ],
        "elss_note": (
            "ELSS units carry a statutory 3-year lock-in from each investment date. "
            f"Units purchased during {label} reach the end of their lock-in on the same "
            "date three years later (each SIP instalment locks separately)."
        ),
    }

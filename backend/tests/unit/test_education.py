"""
Unit tests for the Tax-Education module (G8) — no DB.

Covers the DB-free seams:
  * FY calendar — the 1-April boundary + the statutory key dates.
  * Seed content compliance — no advisory framing, every figure FY-cited, unique slugs.
  * Response schemas — the not-advice disclosure bundle is always present (non-neg #9).

The endpoint+DB paths are covered by tests/integration/test_education.py.
"""

from __future__ import annotations

import datetime

from dhanradar.education.calendar import build_tax_calendar, current_fy, fy_label
from dhanradar.education.content import ARTICLES, EDUCATION_DISCLOSURE
from dhanradar.education.schemas import ArticleDetail, ArticleListResponse, CalendarResponse


# --- FY boundary -------------------------------------------------------------
def test_current_fy_before_april_first():
    assert current_fy(datetime.date(2026, 3, 31)) == (2025, 2026)


def test_current_fy_on_april_first():
    assert current_fy(datetime.date(2026, 4, 1)) == (2026, 2027)


def test_fy_label_format():
    assert fy_label(2025, 2026) == "FY 2025-26 (AY 2026-27)"


def test_calendar_pivots_on_the_april_boundary():
    cal_mar = build_tax_calendar(datetime.date(2026, 3, 31))
    cal_apr = build_tax_calendar(datetime.date(2026, 4, 1))
    assert cal_mar["fy_label"] == "FY 2025-26 (AY 2026-27)"
    assert cal_mar["fy_end"] == "2026-03-31"
    assert cal_apr["fy_label"] == "FY 2026-27 (AY 2027-28)"
    assert cal_apr["fy_end"] == "2027-03-31"


def test_calendar_key_dates_present_and_sorted():
    cal = build_tax_calendar(datetime.date(2025, 9, 1))  # within FY 2025-26
    labels = [k["label"] for k in cal["key_dates"]]
    assert any("Financial year end" in label for label in labels)
    assert any("Income-tax return" in label for label in labels)
    itr = next(k for k in cal["key_dates"] if "Income-tax return" in k["label"])
    assert itr["date"] == "2026-07-31"  # ITR due date for FY 2025-26
    dates = [k["date"] for k in cal["key_dates"]]
    assert dates == sorted(dates)
    assert "elss" in cal["elss_note"].lower()


# --- seed content compliance -------------------------------------------------
def test_seed_content_has_no_advisory_framing():
    """The content must describe rules, never recommend an action (SEBI boundary)."""
    blobs = [EDUCATION_DISCLOSURE]
    for a in ARTICLES:
        blobs += [a["title"], a["summary"], a["body_md"], a.get("source_note") or ""]
    text = "\n".join(blobs).lower()
    for phrase in (
        "you should",
        "should invest",
        "invest in elss to save",
        "we recommend",
        "buy now",
        "best fund",
        "must buy",
        "good time to",
    ):
        assert phrase not in text, f"advisory framing found in seed content: {phrase!r}"


def test_every_article_is_fy_cited_and_well_formed():
    seen: set[str] = set()
    required = {
        "slug", "title", "summary", "body_md", "category", "fy_label", "sort_order", "source_note",
    }
    for a in ARTICLES:
        assert required <= set(a.keys()), f"{a.get('slug')}: missing fields"
        assert a["slug"] not in seen, f"duplicate slug {a['slug']}"
        seen.add(a["slug"])
        assert "2025-26" in a["fy_label"]
        # The FY is cited in the body and/or the dated source note.
        assert "2025-26" in a["body_md"] or "2025-26" in (a["source_note"] or "")


# --- non-neg #9: every response carries the disclosure bundle ----------------
def test_response_schemas_carry_the_disclosure_bundle():
    for model in (ArticleListResponse, ArticleDetail, CalendarResponse):
        fields = set(model.model_fields)
        assert {"disclosure", "not_advice", "disclaimer_version"} <= fields

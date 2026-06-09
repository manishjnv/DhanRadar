"""
DhanRadar — Tax-Education service (G8).

Reads the `education` schema only (no cross-module access; no writes from the read
path). Every response is assembled WITH the not-advice disclosure bundle (non-neg
#9). `NOT_ADVICE` + `DISCLAIMER_VERSION` are imported read-only from the shared
compliance constants; the contextual education disclosure text is the module's own.
"""

from __future__ import annotations

import datetime
from typing import Any

from dhanradar.education.calendar import build_tax_calendar
from dhanradar.education.content import EDUCATION_DISCLOSURE, EDUCATION_NOT_ADVICE
from dhanradar.education.schemas import (
    ArticleDetail,
    ArticleListResponse,
    ArticleSummary,
    CalendarResponse,
    KeyDateItem,
)
from dhanradar.scoring.engine.schemas import DISCLAIMER_VERSION


def _disc() -> dict:
    # `not_advice` is the education module's own human-readable line — NOT the
    # platform `NOT_ADVICE` marker token, which renders as the bare word otherwise.
    return {
        "disclosure": EDUCATION_DISCLOSURE,
        "not_advice": EDUCATION_NOT_ADVICE,
        "disclaimer_version": DISCLAIMER_VERSION,
    }


async def list_articles(
    db: Any, *, category: str | None = None, fy: str | None = None
) -> ArticleListResponse:
    """List article summaries (optional category + FY-label filters), ordered."""
    from sqlalchemy import select

    from dhanradar.models.education import TaxEducationArticle

    stmt = select(TaxEducationArticle).order_by(
        TaxEducationArticle.sort_order, TaxEducationArticle.title
    )
    if category:
        stmt = stmt.where(TaxEducationArticle.category == category)
    if fy:
        stmt = stmt.where(TaxEducationArticle.fy_label == fy)

    rows = (await db.scalars(stmt)).all()
    return ArticleListResponse(
        articles=[
            ArticleSummary(
                slug=r.slug,
                title=r.title,
                summary=r.summary,
                category=r.category,
                fy_label=r.fy_label,
            )
            for r in rows
        ],
        **_disc(),
    )


async def get_article(db: Any, slug: str) -> ArticleDetail | None:
    """Return one article by slug, or None (caller → RFC7807 404)."""
    from sqlalchemy import select

    from dhanradar.models.education import TaxEducationArticle

    r = await db.scalar(
        select(TaxEducationArticle).where(TaxEducationArticle.slug == slug)
    )
    if r is None:
        return None
    return ArticleDetail(
        slug=r.slug,
        title=r.title,
        summary=r.summary,
        body_md=r.body_md,
        category=r.category,
        fy_label=r.fy_label,
        source_note=r.source_note,
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
        **_disc(),
    )


def get_calendar(today: datetime.date) -> CalendarResponse:
    """Build the FY-aware key-date calendar for ``today`` (pure + DB-free)."""
    cal = build_tax_calendar(today)
    return CalendarResponse(
        fy_label=cal["fy_label"],
        fy_start=cal["fy_start"],
        fy_end=cal["fy_end"],
        key_dates=[KeyDateItem(**k) for k in cal["key_dates"]],
        elss_note=cal["elss_note"],
        **_disc(),
    )

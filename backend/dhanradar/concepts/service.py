"""
DhanRadar — Concept-Explainer service (C1).

Reads the `concepts` schema only (no cross-module access; no writes from the read
path). Every response is assembled WITH the not-advice disclosure bundle (non-neg
#9). `DISCLAIMER_VERSION` is imported read-only from the shared compliance
constants (same precedent as the education module); the contextual concepts
disclosure text is the module's own.
"""

from __future__ import annotations

from typing import Any

from dhanradar.concepts.content import CONCEPTS_DISCLOSURE, CONCEPTS_NOT_ADVICE
from dhanradar.concepts.schemas import ConceptDetail, ConceptListResponse, ConceptSummary
from dhanradar.scoring.engine.schemas import DISCLAIMER_VERSION


def _disc() -> dict:
    # `not_advice` is the concepts module's own human-readable line — NOT the
    # platform `NOT_ADVICE` marker token, which renders as the bare word otherwise.
    return {
        "disclosure": CONCEPTS_DISCLOSURE,
        "not_advice": CONCEPTS_NOT_ADVICE,
        "disclaimer_version": DISCLAIMER_VERSION,
    }


async def list_concepts(db: Any, *, category: str | None = None) -> ConceptListResponse:
    """List concept summaries (optional category filter), in pedagogical order."""
    from sqlalchemy import select

    from dhanradar.models.concepts import ConceptExplainer

    stmt = select(ConceptExplainer).order_by(
        ConceptExplainer.sort_order, ConceptExplainer.title
    )
    if category:
        stmt = stmt.where(ConceptExplainer.category == category)

    rows = (await db.scalars(stmt)).all()
    return ConceptListResponse(
        concepts=[
            ConceptSummary(
                slug=r.slug,
                title=r.title,
                summary=r.summary,
                category=r.category,
            )
            for r in rows
        ],
        **_disc(),
    )


async def get_concept(db: Any, slug: str) -> ConceptDetail | None:
    """Return one concept by slug, or None (caller → RFC7807 404)."""
    from sqlalchemy import select

    from dhanradar.models.concepts import ConceptExplainer

    r = await db.scalar(select(ConceptExplainer).where(ConceptExplainer.slug == slug))
    if r is None:
        return None
    return ConceptDetail(
        slug=r.slug,
        title=r.title,
        summary=r.summary,
        body_md=r.body_md,
        category=r.category,
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
        **_disc(),
    )

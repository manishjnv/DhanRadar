"""
DhanRadar — Tax-Education seed loader (G8).

Idempotently upserts the authored articles from `content.py` into
`education.tax_education_articles`. Safe to re-run — existing rows are updated by
slug (content edits propagate; nothing is duplicated). Run at deploy after the
migration:

    python -m dhanradar.education.seed
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from dhanradar.education.content import ARTICLES

logger = logging.getLogger(__name__)


async def seed_articles(db: Any) -> int:
    """Upsert every authored article by slug. Returns the number processed."""
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.models.education import TaxEducationArticle

    count = 0
    for article in ARTICLES:
        stmt = insert(TaxEducationArticle).values(**article)
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={k: article[k] for k in article if k != "slug"} | {"updated_at": func.now()},
        )
        await db.execute(stmt)
        count += 1
    await db.commit()
    return count


async def _run() -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from dhanradar.db import engine

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        count = await seed_articles(db)
    logger.info("education: seeded %d tax articles", count)
    print(f"education: seeded {count} tax articles")  # noqa: T201 — CLI feedback


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

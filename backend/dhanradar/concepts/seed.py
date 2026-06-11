"""
DhanRadar — Concept-Explainer seed loader (C1).

Idempotently upserts the authored explainers from `content.py` into
`concepts.concept_explainers`. Safe to re-run — existing rows are updated by
slug (content edits propagate; nothing is duplicated). Run at deploy after the
migration:

    python -m dhanradar.concepts.seed
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from dhanradar.concepts.content import CONCEPTS

logger = logging.getLogger(__name__)


async def seed_concepts(db: Any) -> int:
    """Upsert every authored concept by slug. Returns the number processed."""
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.models.concepts import ConceptExplainer

    count = 0
    for concept in CONCEPTS:
        stmt = insert(ConceptExplainer).values(**concept)
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={k: concept[k] for k in concept if k != "slug"} | {"updated_at": func.now()},
        )
        await db.execute(stmt)
        count += 1
    await db.commit()
    return count


async def _run() -> None:
    from dhanradar.db import TaskSessionLocal

    async with TaskSessionLocal() as db:
        count = await seed_concepts(db)
    logger.info("concepts: seeded %d concept explainers", count)
    print(f"concepts: seeded {count} concept explainers")  # noqa: T201 — CLI feedback


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

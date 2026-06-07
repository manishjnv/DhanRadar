"""Onboarding service — SOLE writer of auth.users.risk_profile.

Module isolation contract:
  - This module MUST NEVER import anything from dhanradar.scoring, dhanradar.billing,
    or dhanradar.mf.  risk_profile must never flow toward the scoring engine.
  - Only dhanradar.models.auth.User + SQLAlchemy are imported here.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.models.auth import User
from dhanradar.onboarding.quiz import score_answers


async def set_risk_profile(
    db: AsyncSession,
    user_id: str,
    answers: list[int],
) -> str:
    """Compute and persist the risk profile for ``user_id``.

    This is the SOLE writer of auth.users.risk_profile.  It must never read
    or import the scoring engine — risk_profile is an input to onboarding only.

    Raises:
        ValueError: if ``user_id`` is not a valid UUID or ``answers`` fail
                    the quiz validation rules.
    """
    profile = score_answers(answers)  # raises ValueError on bad input

    # Fail closed on a malformed user_id (not a 500 — caught at the route layer).
    uid = UUID(user_id)  # raises ValueError if malformed

    await db.execute(
        update(User).where(User.id == uid).values(risk_profile=profile)
    )
    await db.commit()

    return profile

"""Create compliance.ai_output_feedback table for user feedback on AI outputs.

Revision ID: 0049
Revises: 0048
Create Date: 2026-06-24
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_output_feedback",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "audit_id",
            PG_UUID(as_uuid=True),
            nullable=False,
            comment="Soft ref to compliance.ai_recommendation_audit.id",
        ),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column(
            "feedback_text",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # DB-level length cap matches Pydantic max_length=500 (defense in depth).
        sa.CheckConstraint(
            "feedback_text IS NULL OR char_length(feedback_text) <= 500",
            name="ck_ai_output_feedback_text_len",
        ),
        schema="compliance",
    )
    # One vote per user per audit output — prevents duplicate-vote spam.
    op.create_index(
        "uq_ai_output_feedback_per_user_audit",
        "ai_output_feedback",
        ["audit_id", "user_id"],
        unique=True,
        schema="compliance",
    )
    op.create_index(
        "ix_ai_output_feedback_audit_id",
        "ai_output_feedback",
        ["audit_id"],
        schema="compliance",
    )
    op.create_index(
        "ix_ai_output_feedback_user_id",
        "ai_output_feedback",
        ["user_id"],
        schema="compliance",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_output_feedback_user_id",
        table_name="ai_output_feedback",
        schema="compliance",
    )
    op.drop_index(
        "ix_ai_output_feedback_audit_id",
        table_name="ai_output_feedback",
        schema="compliance",
    )
    op.drop_index(
        "uq_ai_output_feedback_per_user_audit",
        table_name="ai_output_feedback",
        schema="compliance",
    )
    op.drop_table("ai_output_feedback", schema="compliance")
